# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
QT Login dialog for authenticating to a Shotgun server.

--------------------------------------------------------------------------------
NOTE! This module is part of the authentication library internals and should
not be called directly. Interfaces and implementation of this module may change
at any point.
--------------------------------------------------------------------------------
"""

from .ui import resources_rc # noqa
from .ui import login_dialog
from . import session_cache
from ..util.shotgun import connection
from ..util import login
from .errors import AuthenticationError
from .ui.qt_abstraction import QtGui, QtCore, QtNetwork, QtWebKit
from tank_vendor import shotgun_api3
from .sso_saml2 import SsoSaml2Toolkit, SsoSaml2MissingQtModuleError, is_sso_enabled_on_site
from .. import LogManager

logger = LogManager.get_logger(__name__)

# Name used to identify the client application when connecting via SSO to Shotugn.
PRODUCT_IDENTIFIER = "toolkit"

# Checking for SSO support on a site takes a few moments. When the user enters
# a Shotgun site URL, we check for SSO support (and update the GUI) only after
# the user has stopped for longer than the delay (in ms).
USER_INPUT_DELAY_BEFORE_SSO_CHECK = 300

# Let's put at 5 seconds the maximum time we might wait for a SSO check thread.
THREAD_WAIT_TIMEOUT_MS = 5000


class QuerySiteAndUpdateUITask(QtCore.QThread):
    """
    This class uses a different thread to query if SSO is enabled or not.

    We use a different thread due to the time the call can take, and
    to avoid blocking the main GUI thread.
    """

    def __init__(self, parent, http_proxy=None):
        """
        Constructor.
        """
        QtCore.QThread.__init__(self, parent)
        self._url_to_test = ""
        self._sso_enabled = False
        self._http_proxy = http_proxy

    @property
    def sso_enabled(self):
        """Bool R/W property."""
        return self._sso_enabled

    @sso_enabled.setter
    def sso_enabled(self, value):
        self._sso_enabled = value

    @property
    def url_to_test(self):
        """String R/W property."""
        return self._url_to_test

    @url_to_test.setter
    def url_to_test(self, value):
        self._url_to_test = value

    def run(self):
        """
        Runs the thread.
        """
        self.sso_enabled = is_sso_enabled_on_site(shotgun_api3, self.url_to_test, self._http_proxy)


class LoginDialog(QtGui.QDialog):
    """
    Dialog for getting user credentials.
    """

    # Formatting required to display error messages.
    ERROR_MSG_FORMAT = "<font style='color: rgb(252, 98, 70);'>%s</font>"

    def __init__(
        self,
        is_session_renewal, hostname=None, login=None, fixed_host=False, http_proxy=None,
        parent=None, session_metadata=None
    ):
        """
        Constructs a dialog.

        :param is_session_renewal: Boolean indicating if we are renewing a session or authenticating a user from
            scratch.
        :param hostname: The string to populate the site field with. If None, the field will be empty.
        :param login: The string to populate the login field with. If None, the field will be empty.
        :param fixed_host: Indicates if the hostname can be changed. Defaults to False.
        :param http_proxy: The proxy server to use when testing authentication. Defaults to None.
        :param parent: The Qt parent for the dialog (defaults to None)
        :param session_metadata: Metadata used in the context of SSO. This is an obscure blob of data.
        """
        QtGui.QDialog.__init__(self, parent)

        qt_modules = {
            "QtCore": QtCore,
            "QtGui": QtGui,
            "QtNetwork": QtNetwork,
            "QtWebKit": QtWebKit,
        }
        try:
            self._sso_saml2 = SsoSaml2Toolkit("SSO Login", qt_modules=qt_modules)
        except SsoSaml2MissingQtModuleError as e:
            logger.info("SSO login not supported due to missing Qt module: %s" % e)
            self._sso_saml2 = None

        hostname = hostname or ""
        login = login or ""

        self._is_session_renewal = is_session_renewal
        self._session_metadata = session_metadata
        self._use_sso = False

        # setup the gui
        self.ui = login_dialog.Ui_LoginDialog()
        self.ui.setupUi(self)

        # Set the title
        self.setWindowTitle("Shotgun Login")

        # Assign credentials
        self._http_proxy = http_proxy

        recent_hosts = session_cache.get_recent_hosts()
        # If we have a recent host and it's not in the list, add it. This can happen if a user logs
        # on and while the process is running the host is removed from the host list.
        if hostname and hostname not in recent_hosts:
            recent_hosts.insert(0, hostname)

        self.ui.site.set_recent_items(recent_hosts)
        self.ui.site.set_selection(hostname)

        # Apply the stylesheet manually, Qt doesn't see it otherwise...
        COMPLETER_STYLE = self.styleSheet() + (
            "\n\nQWidget {"
            "font-size: 12px;"
            "}"
        )
        self.ui.site.set_style_sheet(COMPLETER_STYLE)
        self.ui.site.set_placeholder_text("example.shotgunstudio.com")
        self.ui.login.set_style_sheet(COMPLETER_STYLE)
        self.ui.login.set_placeholder_text("login")

        self._populate_user_dropdown(recent_hosts[0] if recent_hosts else None)

        # Timer to update the GUI according to the URL, if SSO is supported or not.
        # This is to make the UX smoother, as we do not check after each character
        # typed, but instead wait for a period of inactivity from the user.
        self._url_changed_timer = QtCore.QTimer(self)
        self._url_changed_timer.setSingleShot(True)
        self._url_changed_timer.timeout.connect(self._update_ui_according_to_sso_support)

        # If the host is fixed, disable the site textbox.
        if fixed_host:
            self._disable_text_widget(
                self.ui.site,
                "The Shotgun site has been predefined and cannot be modified."
            )

        # Disable keyboard input in the site and login boxes if we are simply renewing the session.
        if is_session_renewal:
            self._disable_text_widget(
                self.ui.site,
                "You are renewing your session: you can't change your host.")
            self._disable_text_widget(
                self.ui.login,
                "You are renewing your session: you can't change your login."
            )
            self._set_login_message("Your session has expired. Please enter your password.")
        else:
            self._set_login_message("Please enter your credentials.")

        # Set the focus appropriately on the topmost line edit that is empty.
        if self._get_current_site():
            if self._get_current_user():
                self.ui.password.setFocus(QtCore.Qt.OtherFocusReason)
            else:
                self.ui.login.setFocus(QtCore.Qt.OtherFocusReason)

        # Select the right first page.
        self.ui.stackedWidget.setCurrentWidget(self.ui.login_page)

        # hook up signals
        self.ui.sign_in.clicked.connect(self._ok_pressed)
        self.ui.stackedWidget.currentChanged.connect(self._current_page_changed)

        self.ui.verify_2fa.clicked.connect(self._verify_2fa_pressed)
        self.ui.use_backup.clicked.connect(self._use_backup_pressed)

        self.ui.verify_backup.clicked.connect(self._verify_backup_pressed)
        self.ui.use_app.clicked.connect(self._use_app_pressed)

        self.ui.forgot_password_link.linkActivated.connect(self._link_activated)

        self.ui.site.lineEdit().editingFinished.connect(self._strip_whitespaces)
        self.ui.login.lineEdit().editingFinished.connect(self._strip_whitespaces)
        self.ui._2fa_code.editingFinished.connect(self._strip_whitespaces)
        self.ui.backup_code.editingFinished.connect(self._strip_whitespaces)

        # While the user is typing, check the SSOness of the site so we can
        # show or hide the login and password fields.
        self.ui.site.lineEdit().textEdited.connect(self._site_url_changing)
        # If a site has been selected, we need to update the login field.
        self.ui.site.activated.connect(self._on_site_changed)
        self.ui.site.lineEdit().editingFinished.connect(self._on_site_changed)

        self._query_task = QuerySiteAndUpdateUITask(self, http_proxy)
        self._query_task.finished.connect(self._toggle_sso)
        self._update_ui_according_to_sso_support()

        # We want to wait until we know if the site uses SSO or not, to avoid
        # flickering GUI.
        if not self._query_task.wait(THREAD_WAIT_TIMEOUT_MS):
            logger.warning("Timed out awaiting check for SSO support on the site: %s" % self._get_current_site())

    def __del__(self):
        """
        Destructor.
        """
        # We want to clean up any running qthread.
        self._query_task.wait()

    def _get_current_site(self):
        """
        Retrieves the properly filtered site name from the site combo box.

        :returns: The site to connect to.
        """
        return connection.sanitize_url(
            self.ui.site.currentText().strip()
        ).encode("utf-8")

    def _get_current_user(self):
        """
        Retrieves the properly filtered login from the login combo box.

        :returns: The login to use for authentication.
        """
        return self.ui.login.currentText().strip().encode("utf-8")

    def _update_ui_according_to_sso_support(self):
        """
        Updates the GUI if SSO is supported or not, hiding or showing the username/password fields.
        """
        # Only update the GUI if we were able to initialize the sam2sso module.
        if self._sso_saml2:
            self._query_task.url_to_test = self._get_current_site()
            self._query_task.start()

    def _site_url_changing(self, text):
        """
        Starts a timer to wait until the user stops entering the URL .
        """
        self._url_changed_timer.start(USER_INPUT_DELAY_BEFORE_SSO_CHECK)

    def _on_site_changed(self):
        """
        Called when the user is done editing the site. It will refresh the
        list of recent users.
        """
        self.ui.login.clear()
        self._populate_user_dropdown(self._get_current_site())
        self._update_ui_according_to_sso_support()

    def _populate_user_dropdown(self, site):
        """
        Populate the combo box of users based on a given site.

        :param str site: Site to populate the user list for.
        """
        if site:
            users = session_cache.get_recent_users(site)
            self.ui.login.set_recent_items(users)
        else:
            users = []

        if users:
            # The first user in the list is the most recent, so pick it.
            self.ui.login.set_selection(users[0])
        else:
            self.ui.login.setEditText(login.get_login_name())

    def _strip_whitespaces(self):
        """
        Cleans up a field after editing.
        """
        self.sender().setText(self.sender().text().strip())

    def _link_activated(self, site):
        """
        Clicked when the user presses on the "Forgot your password?" link.
        """
        # Don't use the URL that is set in the link, but the URL set in the
        # text box.
        site = self._get_current_site()

        # Give visual feedback that we are patching the URL before invoking
        # the desktop services.
        self.ui.site.setEditText(site)

        # Launch the browser
        forgot_password = "%s/user/forgot_password" % site
        if not QtGui.QDesktopServices.openUrl(forgot_password):
            self._set_error_message(
                self.ui.message, "Can't open '%s'." % forgot_password
            )

    def _toggle_sso(self):
        """
        Sets up the dialog GUI according to the use of SSO or not.
        """
        # We only update the GUI if there was a change between to mode we
        # are showing and what was detected on the potential target site.
        if self._use_sso != self._query_task.sso_enabled:
            self._use_sso = not self._use_sso
            if self._use_sso:
                self.ui.message.setText("Sign in using your Single Sign-On (SSO) Account.")
                self.ui.site.setFocus(QtCore.Qt.OtherFocusReason)
            else:
                self.ui.message.setText("Please enter your credentials.")

            self.ui.login.setVisible(not self._use_sso)
            self.ui.password.setVisible(not self._use_sso)

    def _current_page_changed(self, index):
        """
        Resets text error message on the destination page.
        :param index: Index of the page changed.
        """
        if self.ui.stackedWidget.indexOf(self.ui._2fa_page) == index:
            self.ui.invalid_code.setText("")
        elif self.ui.stackedWidget.indexOf(self.ui.backup_page) == index:
            self.ui.invalid_backup_code.setText("")

    def _disable_text_widget(self, widget, tooltip_text):
        """
        Disables a widget and adds tooltip to it.
        :param widget: Text editing widget to disable.
        :param toolkit_text: Tooltip text that explains why the widget is disabled.
        """
        widget.lineEdit().setReadOnly(True)
        widget.setEnabled(False)
        widget.setToolTip(tooltip_text)

    def _set_login_message(self, message):
        """
        Set the message in the dialog.
        :param message: Message to display in the dialog.
        """
        self.ui.message.setText(message)

    def exec_(self):
        """
        Displays the window modally.
        """
        # This fixes a weird bug on Qt where calling show() and exec_() might lead
        # to having an invisible modal QDialog and this state freezes the host
        # application. (Require a `pkill -9 applicationName`). The fix in our case
        # is pretty simple, we just have to not call show() before the call to
        # exec_() since it implicitly call exec_().
        #
        # This bug is described here: https://bugreports.qt.io/browse/QTBUG-48248
        if QtCore.__version__.startswith("4."):
            self.show()

        self.raise_()
        self.activateWindow()

        # the trick of activating + raising does not seem to be enough for
        # modal dialogs. So force put them on top as well.
        # On PySide2, or-ring the current window flags with WindowStaysOnTopHint causes the dialog
        # to freeze, so only set the WindowStaysOnTopHint flag as this appears to not disable the
        # other flags.
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        return QtGui.QDialog.exec_(self)

    def result(self):
        """
        Displays a modal dialog asking for the credentials.
        :returns: A tuple of (hostname, username and session token) string if the user authenticated
                  None if the user cancelled.
        """
        if self._session_metadata and self._sso_saml2:
            res = self._sso_saml2.login_attempt(
                host=self._get_current_site(),
                http_proxy=self._http_proxy,
                cookies=self._session_metadata,
                product=PRODUCT_IDENTIFIER,
                use_watchdog=True
            )
            # If the offscreen session renewal failed, show the GUI as a failsafe
            if res == QtGui.QDialog.Accepted:
                return self._sso_saml2.get_session_data()
            else:
                return None

        res = self.exec_()

        if res == QtGui.QDialog.Accepted:
            if self._session_metadata and self._sso_saml2:
                return self._sso_saml2.get_session_data()
            return (self._get_current_site(),
                    self._get_current_user(),
                    self._new_session_token,
                    None)
        else:
            return None

    def _set_error_message(self, widget, message):
        """
        Set the error message in the dialog.

        :param widget: Widget to display the message on.
        :param message: Message to display in red in the dialog.
        """
        widget.setText(self.ERROR_MSG_FORMAT % message)

    def _ok_pressed(self):
        """
        Validate the values, accepting if login is successful and display an error message if not.
        """
        # Wait for any ongoing SSO check thread.
        QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            if not self._query_task.wait(THREAD_WAIT_TIMEOUT_MS):
                logger.warning("Timed out awaiting check for SSO support on the site: %s" % self._get_current_site())
        finally:
            QtGui.QApplication.restoreOverrideCursor()

        # pull values from the gui
        site = self._get_current_site()
        login = self._get_current_user()
        password = self.ui.password.text()

        if site == "https://" or site == "http://":
            self._set_error_message(self.ui.message, "Please enter the address of the site to connect to.")
            self.ui.site.setFocus(QtCore.Qt.OtherFocusReason)
            return

        # Cleanup the URL and update the GUI.
        if self._use_sso and site.startswith("http://"):
            site = "https" + site[4:]
        self.ui.site.setEditText(site)

        if not self._use_sso:
            if len(login) == 0:
                self._set_error_message(self.ui.message, "Please enter your login name.")
                self.ui.login.setFocus(QtCore.Qt.OtherFocusReason)
                return
            if len(password) == 0:
                self._set_error_message(self.ui.message, "Please enter your password.")
                self.ui.password.setFocus(QtCore.Qt.OtherFocusReason)
                return

        try:
            self._authenticate(self.ui.message, site, login, password)
        except shotgun_api3.MissingTwoFactorAuthenticationFault:
            # We need a two factor authentication code, move to the next page.
            self.ui.stackedWidget.setCurrentWidget(self.ui._2fa_page)
        except Exception as e:
            self._set_error_message(self.ui.message, e)

    def _authenticate(self, error_label, site, login, password, auth_code=None):
        """
        Authenticates the user using the passed in credentials.

        :param error_label: Label to display any error raised from the authentication.
        :param site: Site to connect to.
        :param login: Login to use for that site.
        :param password: Password to use with the login.
        :param auth_code: Optional two factor authentication code.

        :raises shotgun_api3.MissingTwoFactorAuthenticationFault: Raised if auth_code was None but was required
            by the server.
        """
        success = False
        try:
            if self._use_sso and self._sso_saml2:
                res = self._sso_saml2.login_attempt(
                    host=site,
                    http_proxy=self._http_proxy,
                    cookies=self._session_metadata,
                    product=PRODUCT_IDENTIFIER
                )
                if res == QtGui.QDialog.Accepted:
                    self._new_session_token = self._sso_saml2.session_id
                    self._session_metadata = self._sso_saml2.cookies
                else:
                    error_msg = self._sso_saml2.session_error
                    if error_msg:
                        raise AuthenticationError(error_msg)
                    return
            else:
                # set the wait cursor
                QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
                QtGui.QApplication.processEvents()

                # try and authenticate
                self._new_session_token = session_cache.generate_session_token(
                    site, login, password, self._http_proxy, auth_code
                )
        except AuthenticationError as e:
            # authentication did not succeed
            self._set_error_message(error_label, e)
        else:
            success = True
        finally:
            # restore the cursor
            QtGui.QApplication.restoreOverrideCursor()
            # dialog is done
            QtGui.QApplication.processEvents()

        # Do not accept while the cursor is overriden, if freezes the dialog.
        if success:
            self.accept()

    def _verify_2fa_pressed(self):
        """
        Called when the Verify button is pressed on the 2fa page.
        """
        self._verify_pressed(self.ui._2fa_code.text(), self.ui.invalid_code)

    def _verify_backup_pressed(self):
        """
        Called when the Verify button is pressed on the backup codes page.
        """
        self._verify_pressed(self.ui.backup_code.text(), self.ui.invalid_backup_code)

    def _verify_pressed(self, code, error_label):
        """
        Validates the code, dismissing the dialog if the login is succesful and displaying an error
        if not.
        :param code: Code entered by the user.
        :param error_label: Label to update if the code is invalid.
        """
        if not code:
            self._set_error_message(error_label, "Please enter your code.")
            return

        site = self._get_current_site()
        login = self._get_current_user()
        password = self.ui.password.text()

        try:
            self._authenticate(error_label, site, login, password, code)
        except Exception as e:
            self._set_error_message(self.ui.message, e)

    def _use_backup_pressed(self):
        """
        Switches to the backup codes page.
        """
        self.ui.stackedWidget.setCurrentWidget(self.ui.backup_page)

    def _use_app_pressed(self):
        """
        Switches to the main two factor authentication page.
        """
        self.ui.stackedWidget.setCurrentWidget(self.ui._2fa_page)
