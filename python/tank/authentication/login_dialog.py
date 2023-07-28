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
import os
import sys
from tank_vendor import shotgun_api3
from tank_vendor import six
from .. import constants
from .web_login_support import get_shotgun_authenticator_support_web_login
from .ui import resources_rc  # noqa
from .ui import login_dialog
from . import constants as auth_constants
from . import session_cache
from ..util.shotgun import connection
from ..util import login
from ..util import LocalFileStorageManager
from .errors import AuthenticationError
from .ui.qt_abstraction import QtGui, QtCore, QtNetwork, QtWebKit, QtWebEngineWidgets
from .unified_login_flow2 import authentication as ulf2_authentication
from .sso_saml2 import (
    SsoSaml2IncompletePySide2,
    SsoSaml2Toolkit,
    SsoSaml2MissingQtModuleError,
    is_autodesk_identity_enabled_on_site,
    is_sso_enabled_on_site,
    is_unified_login_flow_enabled_on_site,
    is_unified_login_flow2_enabled_on_site,
)
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


def _is_running_in_desktop():
    """
    Indicate if we are in the context of the ShotGrid Desktop.

    When the ShotGrid Desktop is used, we want to disregard the value returned
    by the call to `get_shotgun_authenticator_support_web_login()` when the
    target site is using Autodesk Identity.
    """
    executable_name = os.path.splitext(os.path.basename(sys.executable))[0].lower()
    return executable_name in ["shotgun", "shotgrid"]


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
        self._unified_login_flow_enabled = False
        self._unified_login_flow2_enabled = False
        self._http_proxy = http_proxy

    @property
    def sso_enabled(self):
        """returns: `True` if SSO is enabled, `False` otherwise."""
        return self._sso_enabled

    @property
    def autodesk_identity_enabled(self):
        """returns: `True` if Identity is enabled, `False` otherwise."""
        return self._autodesk_identity_enabled

    @property
    def unified_login_flow_enabled(self):
        """returns: `True` if ULF is enabled, `False` otherwise."""
        return self._unified_login_flow_enabled

    @property
    def unified_login_flow2_enabled(self):
        """returns: `True` if ULF2 is enabled, `False` otherwise."""
        return self._unified_login_flow2_enabled

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
        # The site information is cached, so those three calls do not add
        # any significant overhead.
        self._sso_enabled = is_sso_enabled_on_site(self.url_to_test, self._http_proxy)
        self._autodesk_identity_enabled = is_autodesk_identity_enabled_on_site(
            self.url_to_test, self._http_proxy
        )
        self._unified_login_flow_enabled = is_unified_login_flow_enabled_on_site(
            self.url_to_test, self._http_proxy
        )

        self._unified_login_flow2_enabled = is_unified_login_flow2_enabled_on_site(
            self.url_to_test, self._http_proxy
        )


class LoginDialog(QtGui.QDialog):
    """
    Dialog for getting user credentials.
    """

    # Formatting required to display error messages.
    ERROR_MSG_FORMAT = "<font style='color: rgb(252, 98, 70);'>%s</font>"

    def __init__(
        self,
        is_session_renewal,
        hostname=None,
        login=None,
        fixed_host=False,
        http_proxy=None,
        parent=None,
        session_metadata=None,
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
            "QtWebEngineWidgets": QtWebEngineWidgets,
        }
        try:
            self._sso_saml2 = SsoSaml2Toolkit(
                "ShotGrid Web Login", qt_modules=qt_modules
            )
        except SsoSaml2MissingQtModuleError as e:
            logger.warning("Web login not supported due to missing Qt module: %s" % e)
            self._sso_saml2 = None
        except SsoSaml2IncompletePySide2 as e:
            logger.warning(
                "Web login not supported due to missing Qt method/class: %s" % e
            )
            self._sso_saml2 = None

        hostname = hostname or ""
        login = login or ""

        self._is_session_renewal = is_session_renewal
        self._session_metadata = session_metadata
        self._use_web = False
        self._use_local_browser = False

        self._ulf2_task = None

        # setup the gui
        self.ui = login_dialog.Ui_LoginDialog()
        self.ui.setupUi(self)

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
        completer_style = self.styleSheet() + ("\n\nQWidget {" "font-size: 12px;" "}")
        self.ui.site.set_style_sheet(completer_style)
        self.ui.site.set_placeholder_text("example.shotgrid.autodesk.com")
        self.ui.login.set_style_sheet(completer_style)
        self.ui.login.set_placeholder_text("login")

        self._populate_user_dropdown(recent_hosts[0] if recent_hosts else None)

        # Timer to update the GUI according to the URL, if SSO is supported or not.
        # This is to make the UX smoother, as we do not check after each character
        # typed, but instead wait for a period of inactivity from the user.
        self._url_changed_timer = QtCore.QTimer(self)
        self._url_changed_timer.setSingleShot(True)
        self._url_changed_timer.timeout.connect(
            self._update_ui_according_to_sso_support
        )

        # If the host is fixed, disable the site textbox.
        if fixed_host:
            self._disable_text_widget(
                self.ui.site,
                "The ShotGrid site has been predefined and cannot be modified.",
            )

        # Disable keyboard input in the site and login boxes if we are simply renewing the session.
        if is_session_renewal:
            self._disable_text_widget(
                self.ui.site,
                "You are renewing your session: you can't change your host.",
            )
            self._disable_text_widget(
                self.ui.login,
                "You are renewing your session: you can't change your login.",
            )
            self._set_login_message(
                "Your session has expired. Please enter your password."
            )
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

        # Initialize Options menu
        menu = QtGui.QMenu(self.ui.button_options)
        self.ui.button_options.setMenu(menu)
        self.ui.button_options.setVisible(False)

        self.menu_action_ulf2 = QtGui.QAction(
            "Authenticate with your default web browser",
            menu,
        )
        self.menu_action_ulf2.triggered.connect(self._menu_activated_action_ulf2)
        menu.addAction(self.menu_action_ulf2)

        self.menu_action_ulf = QtGui.QAction(
            "Authenticate with the ShotGrid Desktop browser (legacy)",
            menu,
        )
        self.menu_action_ulf.triggered.connect(self._menu_activated_action_web_legacy)
        menu.addAction(self.menu_action_ulf)

        self.menu_action_legacy = QtGui.QAction(
            "Authenticate with your legacy login credentials",
            menu,
        )
        self.menu_action_legacy.triggered.connect(
            self._menu_activated_action_login_creds
        )
        menu.addAction(self.menu_action_legacy)

        menu.addAction("Forgot your password?", self._link_activated)

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

        self.ui.ulf2_msg_help.setOpenExternalLinks(True)
        self.ui.ulf2_msg_help.setText(
            self.ui.ulf2_msg_help.text().format(
                url=constants.SUPPORT_URL,
            )
        )

        self.ui.ulf2_msg_back.linkActivated.connect(self._ulf2_back_pressed)

        # While the user is typing, check the SSOness of the site so we can
        # show or hide the login and password fields.
        self.ui.site.lineEdit().textEdited.connect(self._site_url_changing)
        # If a site has been selected, we need to update the login field.
        self.ui.site.activated.connect(self._on_site_changed)
        self.ui.site.lineEdit().editingFinished.connect(self._on_site_changed)

        self._query_task = QuerySiteAndUpdateUITask(self, http_proxy)
        self._query_task.finished.connect(self._toggle_web)
        self._update_ui_according_to_sso_support()

        # We want to wait until we know if the site uses SSO or not, to avoid
        # flickering GUI.
        if not self._query_task.wait(THREAD_WAIT_TIMEOUT_MS):
            logger.warning(
                "Timed out awaiting check for SSO support on the site: %s"
                % self._get_current_site()
            )

        # Initialize exit confirm message box
        self.confirm_box = QtGui.QMessageBox(
            QtGui.QMessageBox.Question,
            "ShotGrid Login",  # title
            "Would you like to cancel your request?",  # text
            buttons=QtGui.QMessageBox.Yes | QtGui.QMessageBox.No,
            # parent=self,
            # Passing the parent parameter here, in the constructor, makes
            # Nuke versions<=13 crash.
            # Two ways to resolve that:
            #  #1. Create the QMessageBox later (not in the constructor)
            #  #2. Pass the QDialog stylesheet to the QMessageBox since I did
            #      not see any other consequence by not passing the parent
            #      parameter.
            # I chose solution #1, se below.
        )
        # force the QMessageBox to be on top of other dialogs.
        self.confirm_box.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.confirm_box.setInformativeText(
            "The authentication is still in progress and closing this window "
            "will result in canceling your request."
        )

        self.confirm_box.setStyleSheet(self.styleSheet())

    def __del__(self):
        """
        Destructor.
        """
        # We want to clean up any running qthread.
        self._query_task.wait()

    def _confirm_exit(self):
        return self.confirm_box.exec_() == QtGui.QMessageBox.StandardButton.Yes
        # PySide uses "exec_" instead of "exec" because "exec" is a reserved
        # keyword in Python 2.

    def closeEvent(self, event):
        if not self._confirm_exit():
            event.ignore()
            return

        if self._ulf2_task:
            self._ulf2_task.finished.disconnect(self._ulf2_task_finished)
            self._ulf2_task.stop_when_possible()
            self._ulf2_task.wait()
            self._ulf2_task = None

        return super(LoginDialog, self).closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            if not self._confirm_exit():
                event.ignore()
                return

        if self._ulf2_task:
            self._ulf2_task.finished.disconnect(self._ulf2_task_finished)
            self._ulf2_task.stop_when_possible()
            self._ulf2_task.wait()
            self._ulf2_task = None

        return super(LoginDialog, self).keyPressEvent(event)

    def _get_current_site(self):
        """
        Retrieves the properly filtered site name from the site combo box.

        :returns: The site to connect to.
        """
        return six.ensure_str(
            connection.sanitize_url(self.ui.site.currentText().strip())
        )

    def _get_current_user(self):
        """
        Retrieves the properly filtered login from the login combo box.

        :returns: The login to use for authentication.
        """
        return six.ensure_str(self.ui.login.currentText().strip())

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

    def _link_activated(self, site=None):
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

    def _toggle_web(self, method_selected=None):
        """
        Sets up the dialog GUI according to the use of web login or not.
        """
        # We only update the GUI if there was a change between to mode we
        # are showing and what was detected on the potential target site.
        # With a SSO site, we have no choice but to use the web to login.
        use_web = self._query_task.sso_enabled
        use_local_browser = False

        # The user may decide to force the use of the old dialog:
        # - due to graphical issues with Qt and its WebEngine
        # - they need to use the legacy login / passphrase to use a PAT with
        #   Autodesk Identity authentication
        if os.environ.get("SGTK_FORCE_STANDARD_LOGIN_DIALOG"):
            logger.info("Using the standard login dialog with the ShotGrid Desktop")
        else:
            if _is_running_in_desktop():
                use_web = use_web or self._query_task.autodesk_identity_enabled

            # If we have full support for Web-based login, or if we enable it in our
            # environment, use the Unified Login Flow for all authentication modes.
            if get_shotgun_authenticator_support_web_login():
                use_web = use_web or self._query_task.unified_login_flow_enabled

        if self._query_task.unified_login_flow2_enabled:
            site = self._query_task.url_to_test

            if method_selected:
                # Selecting requested mode (credentials, web_legacy or unified_login_flow2)
                if method_selected == auth_constants.METHOD_ULF2:
                    use_local_browser = True

                session_cache.set_preferred_method(site, method_selected)
            elif os.environ.get("SGTK_FORCE_STANDARD_LOGIN_DIALOG"):
                # Selecting legacy auth by default
                pass
            else:
                method = session_cache.get_preferred_method(site)
                if not method or method == auth_constants.METHOD_ULF2:
                    # Select Unified Login Flow 2
                    use_local_browser = True

        # if we are switching from one mode (using the web) to another (not using
        # the web), or vice-versa, we need to update the GUI.
        # In web-based authentication, the web form is in charge of obtaining
        # and validating the user credentials.

        if use_local_browser:
            self._use_web = False
            if self._use_local_browser:
                return  # nothing to do

            self._use_local_browser = not self._use_local_browser

            self.ui.site.setFocus(QtCore.Qt.OtherFocusReason)
            self.ui.login.setVisible(False)
            self.ui.password.setVisible(False)
            self.ui.message.setText(
                "<p>Continue to sign in using your web browser.</p>"
                "<p>After selecting <b>Sign In</b>, your default web browser will "
                "prompt you to approve the authentication request from your "
                "ShotGrid site.</p>"
            )
        elif use_web:
            logger.info("Using the Web Login with the ShotGrid Desktop")
            self._use_local_browser = False
            if self._use_web:
                return  # nothing to do

            self._use_web = not self._use_web

            self.ui.site.setFocus(QtCore.Qt.OtherFocusReason)
            self.ui.login.setVisible(False)
            self.ui.password.setVisible(False)

            if not self._query_task.unified_login_flow2_enabled:
                # Old text
                self.ui.message.setText("Sign in using the Web.")
            else:
                self.ui.message.setText(
                    "<p>Authenticate with the ShotGrid Desktop browser (legacy).</p>"
                    '<p><a style="color:#c0c1c3;" href="{url}">Learn more here</a></p>'.format(
                        url=constants.DOCUMENTATION_URL_LEGACY_AUTHENTICATION,
                    )
                )
        else:
            self._use_web = False
            self._use_local_browser = False

            self.ui.login.setVisible(True)
            self.ui.password.setVisible(True)
            self.ui.message.setText(
                "Please enter your credentials"
                " - "
                '<a style="color:#c0c1c3;" href="{url}">Learn more here</a>'.format(
                    url=constants.DOCUMENTATION_URL_LEGACY_AUTHENTICATION,
                )
            )

        self.ui.forgot_password_link.setVisible(
            not self._query_task.unified_login_flow2_enabled
        )
        self.ui.button_options.setVisible(self._query_task.unified_login_flow2_enabled)
        self.menu_action_ulf.setVisible(use_web)
        self.menu_action_legacy.setVisible(not use_web)

        self.menu_action_ulf2.setEnabled(not self._use_local_browser)
        self.menu_action_ulf.setEnabled(self._use_local_browser)
        self.menu_action_legacy.setEnabled(self._use_local_browser)

    def _menu_activated_action_ulf2(self):
        self._toggle_web(method_selected=auth_constants.METHOD_ULF2)

    def _menu_activated_action_web_legacy(self):
        self._toggle_web(method_selected=auth_constants.METHOD_WEB_LOGIN)

    def _menu_activated_action_login_creds(self):
        self._toggle_web(method_selected=auth_constants.METHOD_BASIC)

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
            profile_location = LocalFileStorageManager.get_site_root(
                self._get_current_site(), LocalFileStorageManager.CACHE
            )
            res = self._sso_saml2.login_attempt(
                host=self._get_current_site(),
                http_proxy=self._http_proxy,
                cookies=self._session_metadata,
                product=PRODUCT_IDENTIFIER,
                use_watchdog=True,
                profile_location=profile_location,
            )
            # If the offscreen session renewal failed, show the GUI as a failsafe
            if res == QtGui.QDialog.Accepted:
                return self._sso_saml2.get_session_data()
            else:
                return None

        res = self.exec_()

        if res == QtGui.QDialog.Accepted:
            if self._use_local_browser and self._ulf2_task:
                return self._ulf2_task.session_info

            if self._session_metadata and self._sso_saml2:
                return self._sso_saml2.get_session_data()
            return (
                self._get_current_site(),
                self._get_current_user(),
                self._new_session_token,
                None,
            )
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
                logger.warning(
                    "Timed out awaiting check for SSO support on the site: %s"
                    % self._get_current_site()
                )
        finally:
            QtGui.QApplication.restoreOverrideCursor()

        # pull values from the gui
        site = self._get_current_site()
        login = self._get_current_user()
        password = self.ui.password.text()

        if site == "https://" or site == "http://":
            self._set_error_message(
                self.ui.message, "Please enter the address of the site to connect to."
            )
            self.ui.site.setFocus(QtCore.Qt.OtherFocusReason)
            return

        # Cleanup the URL and update the GUI.
        if self._use_web and site.startswith("http://"):
            site = "https" + site[4:]
        self.ui.site.setEditText(site)

        if not self._use_web and not self._use_local_browser:
            if len(login) == 0:
                self._set_error_message(
                    self.ui.message, "Please enter your login name."
                )
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
            if self._use_local_browser:
                return self._ulf2_process(site)
            elif self._use_web and self._sso_saml2:
                profile_location = LocalFileStorageManager.get_site_root(
                    site, LocalFileStorageManager.CACHE
                )
                res = self._sso_saml2.login_attempt(
                    host=site,
                    http_proxy=self._http_proxy,
                    cookies=self._session_metadata,
                    product=PRODUCT_IDENTIFIER,
                    profile_location=profile_location,
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

    def _ulf2_process(self, site):
        self._ulf2_task = ULF2_AuthTask(
            self,
            site,
            http_proxy=self._http_proxy,
            product=PRODUCT_IDENTIFIER,
        )
        self._ulf2_task.finished.connect(self._ulf2_task_finished)
        self._ulf2_task.start()

        self.ui.stackedWidget.setCurrentWidget(self.ui.ulf2_page)

    def _ulf2_back_pressed(self):
        """
        Cancel Unified Login Flow 2 authentication and switch page back to login
        """

        self.ui.stackedWidget.setCurrentWidget(self.ui.login_page)
        logger.info("Cancelling web authentication")

        if self._ulf2_task:
            self._ulf2_task.finished.disconnect(self._ulf2_task_finished)
            self._ulf2_task.stop_when_possible()
            self._ulf2_task = None

    def _ulf2_task_finished(self):
        if not self._ulf2_task:
            # Multi-Thread failsafe
            return

        self.ui.stackedWidget.setCurrentWidget(self.ui.login_page)

        if self._ulf2_task.exception:
            self._set_error_message(self.ui.message, self._ulf2_task.exception)
            self._ulf2_task = None
            return

        if not self._ulf2_task.session_info:
            # The task got interrupted somehow.
            return

        self.accept()


class ULF2_AuthTask(QtCore.QThread):
    progressing = QtCore.Signal(str)

    def __init__(self, parent, sg_url, http_proxy=None, product=None):
        super(ULF2_AuthTask, self).__init__(parent)
        self.should_stop = False

        self._sg_url = sg_url
        self._http_proxy = http_proxy
        self._product = product

        # Result object
        self.session_info = None
        self.exception = None

    def run(self):
        try:
            self.session_info = ulf2_authentication.process(
                self._sg_url,
                http_proxy=self._http_proxy,
                product=self._product,
                browser_open_callback=lambda u: QtGui.QDesktopServices.openUrl(u),
                keep_waiting_callback=self.should_continue,
            )
        except AuthenticationError as err:
            self.exception = err

    def should_continue(self):
        return not self.should_stop

    def stop_when_possible(self):
        self.should_stop = True
