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
from shotgun_shared import Saml2Sso, is_sso_enabled_on_site
from .errors import AuthenticationError
from .ui.qt_abstraction import QtGui, QtCore
from tank_vendor.shotgun_api3 import MissingTwoFactorAuthenticationFault
from .. import LogManager

logger = LogManager.get_logger(__name__)

# Name used to identify the client application when connecting via SSO to Shotugn.
PRODUCT_IDENTIFIER = "toolkit"


class LoginDialog(QtGui.QDialog):
    """
    Dialog for getting user credentials.
    """

    # Formatting required to display error messages.
    ERROR_MSG_FORMAT = "<font style='color: rgb(252, 98, 70);'>%s</font>"

    def __init__(self, is_session_renewal, hostname=None, login=None, fixed_host=False, http_proxy=None, parent=None, cookies=None):
        """
        Constructs a dialog.

        :param is_session_renewal: Boolean indicating if we are renewing a session or authenticating a user from
            scratch.
        :param hostname: The string to populate the site field with. If None, the field will be empty.
        :param login: The string to populate the login field with. If None, the field will be empty.
        :param fixed_host: Indicates if the hostname can be changed. Defaults to False.
        :param http_proxy: The proxy server to use when testing authentication. Defaults to None.
        :param parent: The Qt parent for the dialog (defaults to None)
        :param cookies: List of raw cookies. Defaults to empty list.
        """
        QtGui.QDialog.__init__(self, parent)

        self._saml2_sso = Saml2Sso("SSO Login")

        hostname = hostname or ""
        login = login or ""

        self._is_session_renewal = is_session_renewal
        self._cookies = cookies
        self._use_sso = False

        # setup the gui
        self.ui = login_dialog.Ui_LoginDialog()
        self.ui.setupUi(self)

        # Set the title
        self.setWindowTitle("Shotgun Login")

        # Assign credentials
        self._http_proxy = http_proxy
        self.ui.site.setText(hostname)
        self.ui.login.setText(login)

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
            self.ui.use_sso_link.setVisible(False)
        else:
            self._set_login_message("Please enter your credentials.")
            self.ui.use_sso_link.linkActivated.connect(self._toggle_sso)

        # Set the focus appropriately on the topmost line edit that is empty.
        if self.ui.site.text():
            if self.ui.login.text():
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

        self.ui.site.editingFinished.connect(self._strip_whitespaces)
        self.ui.login.editingFinished.connect(self._strip_whitespaces)
        self.ui._2fa_code.editingFinished.connect(self._strip_whitespaces)
        self.ui.backup_code.editingFinished.connect(self._strip_whitespaces)

        url = self.ui.site.text().encode("utf-8")
        if is_sso_enabled_on_site(url):
            self._toggle_sso()

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
        site = connection.sanitize_url(self.ui.site.text())

        # Give visual feedback that we are patching the URL before invoking
        # the desktop services.
        self.ui.site.setText(site)

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
        self._use_sso = not self._use_sso
        if self._use_sso:
            self.ui.message.setText("Sign in using your Single Sign-On (SSO) Account.")
            self.ui.use_sso_link.setText("<a href=\"about:blank\"><span style=\" text-decoration: underline; color:#c0c1c3;\">Use Shotgun Account</span></a>")
        else:
            self.ui.message.setText("Please enter your credentials.")
            self.ui.use_sso_link.setText("<a href=\"about:blank\"><span style=\" text-decoration: underline; color:#c0c1c3;\">Use Single Sign-On (SSO)</span></a>")
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
        widget.setReadOnly(True)
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
        if self._cookies:
            res = self._saml2_sso.on_sso_login_attempt({
                "host": self.ui.site.text().encode("utf-8"),
                "cookies": self._cookies,
                "product": PRODUCT_IDENTIFIER
            }, use_watchdog=True)
            # If the offscreen session renewal failed, show the GUI as a failsafe
            if res == QtGui.QDialog.Accepted:
                return self._saml2_sso.get_session_data()
            else:
                return None

        res = self.exec_()

        if res == QtGui.QDialog.Accepted:
            if self._cookies:
                return self._saml2_sso.get_session_data()
            return (self.ui.site.text().encode("utf-8"),
                    self.ui.login.text().encode("utf-8"),
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
        # pull values from the gui
        site = self.ui.site.text().strip()
        login = self.ui.login.text().strip()
        password = self.ui.password.text()

        if len(site) == 0:
            self._set_error_message(self.ui.message, "Please enter the address of the site to connect to.")
            self.ui.site.setFocus(QtCore.Qt.OtherFocusReason)
            return

        site = connection.sanitize_url(site)

        # Cleanup the URL.
        self.ui.site.setText(site)

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
        except MissingTwoFactorAuthenticationFault:
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

        :raises MissingTwoFactorAuthenticationFault: Raised if auth_code was None but was required
            by the server.
        """
        success = False
        try:
            if self._use_sso:
                res = self._saml2_sso.on_sso_login_attempt({
                    "host": site,
                    "cookies": self._cookies,
                    "product": PRODUCT_IDENTIFIER
                })
                if res == QtGui.QDialog.Accepted:
                    self._new_session_token = self._saml2_sso._session.session_id
                    self._cookies = self._saml2_sso._session.cookies
                else:
                    error_msg = self._saml2_sso.get_session_error()
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

        site = self.ui.site.text().strip()
        login = self.ui.login.text()
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
