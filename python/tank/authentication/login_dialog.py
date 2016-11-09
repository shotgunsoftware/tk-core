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

from .ui import login_dialog
from . import session_cache
from .errors import AuthenticationError
from .ui.qt_abstraction import QtGui, QtCore, QtNetwork
from tank_vendor.shotgun_api3 import MissingTwoFactorAuthenticationFault

from tank_vendor.shotgun_api3.lib.httplib2 import ServerNotFoundError
from tank_vendor.shotgun_api3 import Shotgun


def print_cookie_jar(cookie_jar):
    """print_cookie_jar."""
    print "==== Cookies START ===="
    for cookie in cookie_jar.allCookies():
        print "  --< %s" % cookie.toRawForm()
    print "==== Cookies END ===="


def write_cookie_jar(cookie_jar):
    """write_cookie_jar."""
    with open('cookiejar.txt', 'w') as jar_file:
        for cookie in cookie_jar.allCookies():
            jar_file.write("%s\n" % cookie.toRawForm())


def read_cookie_jar():
    """read_cookie_jar."""
    cookie_list = []
    try:
        with open('cookiejar.txt', 'r') as jar_file:
            for raw_cookie in jar_file.readlines():
                # return QtNetwork.QNetworkCookie.parseCookies(jar_file.readlines())
                cookie_list.append(QtNetwork.QNetworkCookie.parseCookies(raw_cookie)[0])
    except IOError:
        pass
    return cookie_list


class TemporaryEventLoop(QtCore.QEventLoop):
    """
    Local event loop for the session token renewal. The return value of _exec()
    indicates what happen.
    """

    def __init__(self, login_ui, parent=None):
        """
        Constructor
        """
        QtCore.QEventLoop.__init__(self, parent)
        self._webView = login_ui.ui.webView
        self._site = login_ui.ui.site.text()
        self._webView.loadFinished.connect(self._page_onFinished)
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._bail_out)
        self._timer.start(7000)
        # systray.login.connect(self._login)
        # systray.quit.connect(self._quit)

    def _bail_out(self):
        # print "=-=-=-=-=-=-=-=> _bail_out"
        self.exit(QtGui.QDialog.Rejected)

    def _page_onFinished(self):
        """
        Called when "Quit" is selected. Exits the loop.
        """
        url = self._webView.url().toString()
        # print "=-=-=-=-=-=-=-=> _page_onFinished: %s" % url
        if url.startswith(self._site):
            self.exit(QtGui.QDialog.Accepted)
        # else:
        #     self.exit(QtGui.QDialog.Rejected)

    def exec_(self):
        """
        Execute the local event loop. If CmdQ was hit in the past, it will be handled just as if the
        user had picked the Quit menu.

        :returns: The exit code for the loop.
        """
        code = QtCore.QEventLoop.exec_(self)
        # Somebody requested the app to close, so pretend the close menu was picked.
        # print "code: %s" % code
        return code


class LoginDialog(QtGui.QDialog):
    """
    Dialog for getting user credentials.
    """

    # Formatting required to display error messages.
    ERROR_MSG_FORMAT = "<font style='color: rgb(252, 98, 70);'>%s</font>"

    # def __init__(self, is_session_renewal, hostname=None, login=None, fixed_host=False, http_proxy=None, parent=None, no_ui=False):
    def __init__(self, is_session_renewal, hostname=None, login=None, fixed_host=False, http_proxy=None, parent=None, cookies=[], no_gui=False):
        """
        Constructs a dialog.

        :param is_session_renewal: Boolean indicating if we are renewing a session or authenticating a user from
            scratch.
        :param hostname: The string to populate the site field with. If None, the field will be empty.
        :param login: The string to populate the login field with. If None, the field will be empty.
        :param fixed_host: Indicates if the hostname can be changed. Defaults to False.
        :param http_proxy: The proxy server to use when testing authentication. Defaults to None.
        :param parent: The Qt parent for the dialog (defaults to None)
        """
        QtGui.QDialog.__init__(self, parent)

        # self.setWindowState(QtCore.Qt.WindowMinimized)
        hostname = hostname or ""
        login = login or ""

        self._is_session_renewal = is_session_renewal

        self._cookies = cookies
        # print "My cookies: %s" % cookies

        # self._no_gui = True
        self._no_gui = no_gui

        # If we have cookies, let's first try without GUI
        if len(self._cookies) > 0:
            self._no_gui = True

        # setup the gui
        self.ui = login_dialog.Ui_LoginDialog()
        self.ui.setupUi(self)

        # Set the title
        self.setWindowTitle("Shotgun Login")

        # Assign credentials
        self._http_proxy = http_proxy
        self.ui.site.setText(hostname)
        self.ui.login.setText(login)

        # Set the cookie jar from persistent storage
        # self.cookieList = []

        if fixed_host:
            self._disable_text_widget(
                self.ui.site,
                "The Shotgun site has been predefined and cannot be modified."
            )

        # Disable keyboard input in the site and login boxes if we are simply renewing the session.
        # If the host is fixed, disable the site textbox.
        if is_session_renewal:
            self._disable_text_widget(
                self.ui.site,
                "You are renewing your session: you can't change your host.")
            self._disable_text_widget(
                self.ui.login,
                "You are renewing your session: you can't change your login."
            )

        # Set the focus appropriately on the topmost line edit that is empty.
        if self.ui.site.text():
            if self.ui.login.text():
                self.ui.password.setFocus(QtCore.Qt.OtherFocusReason)
            else:
                self.ui.login.setFocus(QtCore.Qt.OtherFocusReason)

        if self._is_session_renewal:
            self._set_login_message("Your session has expired. Please enter your password.")
        else:
            self._set_login_message("Please enter your credentials.")

        # self._cookies = [
        #     'BIGipServerpool_saml_stg_east_9030=2753701642.17955.0000; domain=saml-stg.autodesk.com; path=/',
        #     'PF=2LqUat3dxwM8A4raLdbvyFUzo8RmRp5oNI4H2uaM8E6n; secure; HttpOnly; domain=saml-stg.autodesk.com; path=/',
        #     'pf-hfa-ADSKFormAdapter-rmu=""; secure; HttpOnly; expires=Tue, 08-Nov-2016 03:14:19 GMT; domain=saml-stg.autodesk.com; path=/',
        #     'csrf_token_u90=B5gF0GpeIPGUqE6Ai5SsnR1Z4PGdRRg4aAF-5tChJ7o; domain=okr-staging.shotgunstudio.com; path=/',
        #     'LB-INFO=3448775434.17955.0000; domain=saml-stg.autodesk.com; path=/',
        #     'totango.heartbeat.last_module=__system; secure; expires=Fri, 11-Nov-2016 03:21:06 GMT; domain=okr-staging.shotgunstudio.com; path=/',
        #     'totango.heartbeat.last_ts=1478575266530; secure; expires=Fri, 11-Nov-2016 03:21:06 GMT; domain=okr-staging.shotgunstudio.com; path=/',
        #     '_session_id=da3453c49a4e1e7b41f947a3b7049f8b; secure; HttpOnly; domain=okr-staging.shotgunstudio.com; path=/',
        # ]
        try:
            self.ui.webView.page().networkAccessManager().cookieJar().setAllCookies(
                [QtNetwork.QNetworkCookie.parseCookies(QtCore.QByteArray.fromBase64(x))[0] for x in self._cookies]
            )
        except TypeError:
            pass

        # Select the right first page.
        # self.cookieList = read_cookie_jar()
        # if len(self.cookieList) > 0:
        #     self.ui.webView.page().networkAccessManager().cookieJar().setAllCookies(self.cookieList)

        # print_cookie_jar(self.ui.webView.page().networkAccessManager().cookieJar())
        # QtWebKit.QWebSettings.globalSettings().setAttribute(QtWebKit.QWebSettings.WebAttribute.DeveloperExtrasEnabled, True)
        # QtWebKit.QWebSettings.globalSettings().setAttribute(QtWebKit.QWebSettings.WebAttribute.LocalStorageEnabled, True)

        url = self.ui.site.text()
        if self._check_sso_enabled(url):
            if self._is_session_renewal:
                url += '/saml/saml_login_request'
            print "URL -> %s (%s)" % (url, 'NO GUI' if self._no_gui else 'GUI')
            self.resize(800, 800)
            self.ui.stackedWidget.setCurrentWidget(self.ui.web_page)
            self.ui.webView.load(url)
        else:
            self.ui.stackedWidget.setCurrentWidget(self.ui.login_page)

        # hook up signals
        self.ui.webView.loadStarted.connect(self._page_onStarted)
        self.ui.webView.loadFinished.connect(self._page_onFinished)

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

    def _check_sso_enabled(self, url):
        """
        Check to see if the web site uses sso.
        @FIXME: This is a horrible hack.
        """

        # Temporary shotgun instance, used only for the purpose of checking
        # the site infos.
        try:
            # info = Shotgun('https://okr-staging.shotgunstudio.com', session_token="xxx").info()
            # info = Shotgun('https://hubertp-studio.shotgunstudio.com', session_token="xxx").info()
            # info = Shotgun('https://hubertp-sso.shotgunstudio.com', session_token="xxx").info()
            info = Shotgun(url, session_token="xxx").info()
            if 'user_authentication_method' in info:
                return info['user_authentication_method'] == 'saml2'
        except ServerNotFoundError:
            # Silently ignore exception
            pass
        return False

    def _sso_login(self):
        pass

    def _page_onStarted(self):
        pass
        # print "_page_onStarted"
        # jar = self.ui.webView.page().networkAccessManager().cookieJar()
        # cookies = jar.allCookies()
        # print ""
        # for cookie in cookies:
        #     print "   %s: %s" % (cookie.name(), cookie.value())

    def _page_onFinished(self):
        site = self.ui.site.text()
        url = self.ui.webView.url().toString()
        # print "_page_onFinished: %s" % url
        if url.startswith(site):
            cookieJar = self.ui.webView.page().networkAccessManager().cookieJar()
            # print_cookie_jar(cookieJar)
            self._cookies = []
            session_token = ""
            for cookie in cookieJar.allCookies():
                self._cookies.append(str(cookie.toRawForm().toBase64()))
                if cookie.name() == '_session_id':
                    session_token = cookie.value()
                # print "  --< %s" % cookie.toRawForm()
            self._authenticate(self.ui.message, site, "", "", session_token=str(session_token))

            # print "Session token: %s (%s)" % (session_token, type(session_token))
            # print "Session cookies: %s" % self._cookies
            # write_cookie_jar(cookieJar)

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
        site = self.ui.site.text()

        # Give visual feedback that we are patching the URL before invoking
        # the desktop services. Desktop Services requires HTTP or HTTPS to be
        # present.
        if len(site.split("://")) == 1:
            site = "https://%s" % site
            self.ui.site.setText(site)

        # Launch the browser
        forgot_password = "%s/user/forgot_password" % site
        if not QtGui.QDesktopServices.openUrl(forgot_password):
            self._set_error_message(
                self.ui.message, "Can't open '%s'." % forgot_password
            )

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

    # def bailOut(self):
    #     print "Bailing out!!!!!  <<<--------"
    #     self.exit(QtGui.QDialog.Rejected)
    #     # self.reject()

    def result(self):
        """
        Displays a modal dialog asking for the credentials.
        :returns: A tuple of (hostname, username and session token) string if the user authenticated
                  None if the user cancelled.
        """

        if self._no_gui:
            # self.timer = QtCore.QTimer(self)
            # self.timer.timeout.connect(self.bailOut)
            # self.timer.start(5000)
            res = TemporaryEventLoop(self).exec_()
            if res == QtGui.QDialog.Rejected:
                print "Fallback"
                res = self.exec_()
        else:
            print "Killroy was here"
            res = self.exec_()

        print "This is res: %s" % res

        if res == QtGui.QDialog.Accepted:
            return (self.ui.site.text().encode("utf-8"),
                    self.ui.login.text().encode("utf-8"),
                    self._new_session_token, self._cookies)
        else:
            return None

    # def renew(self):
    #     """
    #     Displays a modal dialog asking for the credentials.
    #     :returns: A tuple of (hostname, username and session token) string if the user authenticated
    #               None if the user cancelled.
    #     """
    #     print "Killroy was here"
    #     self._is_renew_process = True
    #     print "--> %s" % TemporaryEventLoop(self).exec_()
    #     # if self.exec_() == QtGui.QDialog.Accepted:
    #     #     return (self.ui.site.text().encode("utf-8"),
    #     #             self.ui.login.text().encode("utf-8"),
    #     #             self._new_session_token)
    #     # else:
    #     #     return None

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
        site = self.ui.site.text()
        login = self.ui.login.text()
        password = self.ui.password.text()

        if len(site) == 0:
            self._set_error_message(self.ui.message, "Please enter the address of the site to connect to.")
            return
        if len(login) == 0:
            self._set_error_message(self.ui.message, "Please enter your login name.")
            return
        if len(password) == 0:
            self._set_error_message(self.ui.message, "Please enter your password.")
            return

        # if not protocol specified assume https
        if len(site.split("://")) == 1:
            site = "https://%s" % site
            self.ui.site.setText(site)

        try:
            self._authenticate(self.ui.message, site, login, password)
        except MissingTwoFactorAuthenticationFault:
            # We need a two factor authentication code, move to the next page.
            self.ui.stackedWidget.setCurrentWidget(self.ui._2fa_page)
        except Exception, e:
            self._set_error_message(self.ui.message, e)

    def _authenticate(self, error_label, site, login, password, auth_code=None, session_token=None):
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
            # set the wait cursor
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            QtGui.QApplication.processEvents()

            if session_token is None:
                # try and authenticate
                self._new_session_token = session_cache.generate_session_token(
                    site, login, password, self._http_proxy, auth_code
                )
            else:
                self._new_session_token = session_token
        except AuthenticationError, e:
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

        site = self.ui.site.text()
        login = self.ui.login.text()
        password = self.ui.password.text()

        try:
            self._authenticate(error_label, site, login, password, code)
        except Exception, e:
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
