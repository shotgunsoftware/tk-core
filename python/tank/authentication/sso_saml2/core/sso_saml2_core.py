# Copyright (c) 2017 Autodesk.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.
"""
Module to support Web login via a web browser and automated session renewal.
"""

# pylint: disable=line-too-long
# pylint: disable=no-self-use
# pylint: disable=too-many-instance-attributes

import base64
import logging
import os
import sys
import time

try:
    # For Python 2/3 compatibility without a dependency on six, we'll just try
    # to import SimpleCookie as in Python 2...
    from http.cookies import SimpleCookie
except ImportError:
    # and fall back to its Python 3 location if not found.
    from Cookie import SimpleCookie

from .authentication_session_data import AuthenticationSessionData
from .errors import (
    SsoSaml2MissingQtCore,
    SsoSaml2MissingQtGui,
    SsoSaml2MissingQtNetwork,
    SsoSaml2MissingQtWebKit,
)
from .utils import (
    _decode_cookies,
    _encode_cookies,
    _sanitize_http_proxy,
    get_csrf_key,
    get_csrf_token,
    get_logger,
    get_saml_claims_expiration,
    get_session_id,
    get_user_name,
)

try:
    from .username_password_dialog import UsernamePasswordDialog
except ImportError:
    # Silently ignore the import error, as we are likely not in a Qt
    # environment.
    UsernamePasswordDialog = None


# Error messages for events.
HTTP_CANT_CONNECT_TO_SHOTGUN = "Cannot Connect To Shotgun site."
HTTP_AUTHENTICATE_REQUIRED = "Valid credentials are required."
HTTP_AUTHENTICATE_SSO_NOT_UPPORTED = "SSO not supported or enabled on that site."
HTTP_CANT_AUTHENTICATE_SSO_TIMEOUT = (
    "Time out attempting to authenticate to SSO service."
)
HTTP_CANT_AUTHENTICATE_SSO_NO_ACCESS = (
    "You have not been granted access to the Shotgun site."
)

# Timer related values.
# @TODO: parametrize these and add environment variable overload.
WATCHDOG_TIMEOUT_MS = 5000
PREEMPTIVE_RENEWAL_THRESHOLD = 0.9
SHOTGUN_SSO_RENEWAL_INTERVAL = 5000

# Some IdP (Identity Providers) will use JavaScript code which makes use of ES6.
# Our Qt4 environment is unfortunately missing some definitions which we need to
# inject prior to running the IdP code.
# The reference for this code is:
#     https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_objects/Function/bind#Polyfill
FUNCTION_PROTOTYPE_BIND_POLYFILL = """
    // Yes, it does work with `new funcA.bind(thisArg, args)`
    if (!Function.prototype.bind) (function(){
      var ArrayPrototypeSlice = Array.prototype.slice;
      Function.prototype.bind = function(otherThis) {
        if (typeof this !== 'function') {
          // closest thing possible to the ECMAScript 5
          // internal IsCallable function
          throw new TypeError('Function.prototype.bind - what is trying to be bound is not callable');
        }

        var baseArgs= ArrayPrototypeSlice .call(arguments, 1),
            baseArgsLength = baseArgs.length,
            fToBind = this,
            fNOP    = function() {},
            fBound  = function() {
              baseArgs.length = baseArgsLength; // reset to default base arguments
              baseArgs.push.apply(baseArgs, arguments);
              return fToBind.apply(
                     fNOP.prototype.isPrototypeOf(this) ? this : otherThis, baseArgs
              );
            };

        if (this.prototype) {
          // Function.prototype doesn't have a prototype property
          fNOP.prototype = this.prototype;
        }
        fBound.prototype = new fNOP();

        return fBound;
      };
    })();
"""


class SsoSaml2Core(object):
    """Performs Shotgun Web login and pre-emptive renewal for SSO sessions."""

    # login paths, used by the Unified Login Flow.
    renew_path = "/auth/renew"
    landing_path = "/auth/landing"

    def __init__(self, window_title="Web Login", qt_modules=None):
        """
        Create a Web login dialog, using a Web-browser like environment.

        :param window_title: Title to use for the window.
        :param qt_modules:   a dictionnary of required Qt modules.
                             For Qt4/PySide, we require modules QtCore, QtGui, QtNetwork and QtWebKit

        :returns: The SsoSaml2Core oject.
        """
        qt_modules = qt_modules or {}

        self._logger = get_logger()
        self._logger.debug("Constructing SSO dialog: %s", window_title)

        # pylint: disable=invalid-name
        QtCore = self._QtCore = qt_modules.get("QtCore")  # noqa
        QtGui = self._QtGui = qt_modules.get("QtGui")  # noqa
        QtNetwork = self._QtNetwork = qt_modules.get("QtNetwork")  # noqa
        QtWebKit = self._QtWebKit = qt_modules.get("QtWebKit")  # noqa

        if QtCore is None:
            raise SsoSaml2MissingQtCore("The QtCore module is unavailable")

        if QtGui is None:
            raise SsoSaml2MissingQtGui("The QtGui module is unavailable")

        if QtNetwork is None:
            raise SsoSaml2MissingQtNetwork("The QtNetwork module is unavailable")

        if QtWebKit is None:
            raise SsoSaml2MissingQtWebKit("The QtWebKit module is unavailable")

        class TKWebPage(QtWebKit.QWebPage):
            """
            Wrapper class to better control the behaviour when clicking on links
            in the Qt web browser. If we are asked to open a new tab/window, then
            we defer the page to the external browser.

            We need to open some links in an external window so as to avoid
            breaking the authentication flow just to visit an external link.
            Some examples of links that the user may see which we want to open
            externally:
             - Term of use and conditions,
             - Download of the Google/Duo authenticator app
             - Any other links which may be presented by SSO Providers
            """

            def __init__(self, parent=None):
                """
                Class Constructor.
                """
                get_logger().debug("TKWebPage.__init__")
                super(TKWebPage, self).__init__(parent)

            def __del__(self):
                """
                Class Destructor.
                """
                get_logger().debug("TKWebPage.__del__")

            def acceptNavigationRequest(self, frame, request, n_type):  # noqa
                """
                Overloaded method, to properly control the behavioir of clicking on
                links.
                :param frame:   QWebFrame where the navigation is requested.
                                Will be 'None' if the intent is to have the page
                                open in a new tab or window.
                :param request: QNetworkRequest which we must accept/refuse.
                :param n_type:  NavigationType (LinkClicked, FormSubmitted, etc.)
                :returns:       A boolean indicating if we accept or refuse the request.
                """
                get_logger().debug(
                    "NavigationRequest, destination and reason: %s (%s)",
                    request.url().toString(),
                    n_type,
                )
                # A null frame means : open a new window/tab. so we just farm out
                # the request to the external browser.
                if (
                    frame is None
                    and n_type
                    == QtWebKit.QWebPage.NavigationType.NavigationTypeLinkClicked
                ):
                    QtGui.QDesktopServices.openUrl(request.url())
                    return False
                # Otherwise we accept the default behaviour.
                return QtWebKit.QWebPage.acceptNavigationRequest(
                    self, frame, request, n_type
                )

        self._event_data = None
        self._sessions_stack = []
        self._session_renewal_active = False

        self._dialog = QtGui.QDialog()
        self._dialog.setWindowTitle(window_title)
        self._dialog.finished.connect(self.on_dialog_closed)

        self._view = QtWebKit.QWebView(self._dialog)
        self._view.setPage(TKWebPage(self._dialog))
        self._view.page().networkAccessManager().authenticationRequired.connect(
            self.on_authentication_required
        )
        self._view.loadFinished.connect(self.on_load_finished)

        # We want to inject custom JavaScript code before any code is
        # executed in the loaded web pages. This is to polyfill any
        # missing functionality.
        frame = self._view.page().currentFrame()
        frame.javaScriptWindowObjectCleared.connect(self._polyfill)

        # Purposely disable the 'Reload' contextual menu, as it should not be
        # used for SSO. Reloading the page confuses the server.
        self._view.page().action(QtWebKit.QWebPage.Reload).setVisible(False)

        # Ensure that the background color is not controlled by the login page.
        # We want to be able to display any login dialog page without having
        # the night theme of the SG Desktop impacting it. White is the safest
        # background color.
        self._view.setStyleSheet("background-color:white;")

        # The context : in some special cases, Shotgun will take you into an alternate
        # login flow. E.g. when you need to change your password, enter a 2FA value,
        # link your SSO account with an existing account on the site, etc.
        #
        # The issue : when using a non-approved browser, Shotgun will display a
        # warning stating that your browser is not supported. This is fine should
        # you be interacting with the whole site. But in our case, we only
        # navigate the login flow; presenting relatively simple pages. The warning
        # is not warranted. The browser used is dependent on the version of Qt/PySide
        # being used and we have little or no control over it.
        #
        # The solution : hide the warning by overriding the CSS of the page.
        # Fixing Shotgun to recognize the user-agent used by the different version
        # of Qt so that the warning is not displayed would be a tedious task. The
        # present solution is simpler, with the only drawback being the dependency
        # on the name of the div for the warning. No error is generated
        # if that div.browser_not_approved is not present in the page.
        #
        # Worst case scenario : should Shotgun modify how the warning is displayed
        # it would show up in the page.
        css_style = base64.b64encode(
            "div.browser_not_approved { display: none !important; }"
        )
        url = QtCore.QUrl("data:text/css;charset=utf-8;base64," + css_style)
        self._view.settings().setUserStyleSheetUrl(url)

        # Threshold percentage of the SSO session duration, at which
        # time the pre-emptive renewal operation should be started.
        # @TODO: Make threshold parameter configurable.
        self._sso_preemptive_renewal_threshold = PREEMPTIVE_RENEWAL_THRESHOLD

        # We use the _sso_countdown_timer so that it fires once. Its purpose
        # is to start the other _sso_renew_timer. It fires once at an interval
        # of '0', which means 'whenever there are no event waiting in the
        # queue'. The intent is that it will execute the actual (and costly)
        # renewal at a time when the main event loop is readily available.
        #
        # The _sso_countdown_timer will be re-started in on_renew_sso_session.
        # Thus re-starting the chain of reneal events.
        self._sso_countdown_timer = QtCore.QTimer(self._dialog)
        self._sso_countdown_timer.setSingleShot(True)
        self._sso_countdown_timer.timeout.connect(self.on_schedule_sso_session_renewal)

        self._sso_renew_timer = QtCore.QTimer(self._dialog)
        self._sso_renew_timer.setInterval(0)
        self._sso_renew_timer.setSingleShot(True)
        self._sso_renew_timer.timeout.connect(self.on_renew_sso_session)

        # Watchdog timer to detect abnormal conditions during SSO
        # session renewal.
        # If timeout occurs, then the renewal is considered to have
        # failed, therefore the operation is aborted and recovery
        # by interactive authentication is initiated.
        # @TODO: Make watchdog timer duration configurable.
        self._sso_renew_watchdog_timeout_ms = WATCHDOG_TIMEOUT_MS
        self._sso_renew_watchdog_timer = QtCore.QTimer(self._dialog)
        self._sso_renew_watchdog_timer.setInterval(self._sso_renew_watchdog_timeout_ms)
        self._sso_renew_watchdog_timer.setSingleShot(True)
        self._sso_renew_watchdog_timer.timeout.connect(
            self.on_renew_sso_session_timeout
        )

        # We need a way to trace the current status of our login process.
        self._login_status = 0

        # For debugging purposes
        # @TODO: Find a better way than to use the log level
        if (
            self._logger.level == logging.DEBUG
            or "SHOTGUN_SSO_DEVELOPER_ENABLED" in os.environ
        ):
            self._logger.debug(
                "Using developer mode. Disabling strict SSL mode, enabling developer tools and local storage."
            )
            # Disable SSL validation, useful when using a VM or a test site.
            config = QtNetwork.QSslConfiguration.defaultConfiguration()
            config.setPeerVerifyMode(QtNetwork.QSslSocket.VerifyNone)
            QtNetwork.QSslConfiguration.setDefaultConfiguration(config)

            # Adds the Developer Tools option when right-clicking
            QtWebKit.QWebSettings.globalSettings().setAttribute(
                QtWebKit.QWebSettings.WebAttribute.DeveloperExtrasEnabled, True
            )
            QtWebKit.QWebSettings.globalSettings().setAttribute(
                QtWebKit.QWebSettings.WebAttribute.LocalStorageEnabled, True
            )

    def __del__(self):
        """Destructor."""
        # We want to track destruction of the dialog in the logs.
        self._logger.debug("Destroying SSO dialog")

    @property
    def _session(self):
        """
        Getter for the current session.

        Returns the current session, if any. The session provides information
        on the current context (host, user ID, etc.)

        :returns: The current session.
        """
        return self._sessions_stack[-1] if self._sessions_stack else None

    def start_new_session(self, session_data):
        """
        Create a new session, based on the data provided.

        :param session_data: Initial session data to use.
                             A dictionary with a 'event', 'host' and 'cookies' entries.
        """
        self._logger.debug("Starting a new session")
        self._sessions_stack.append(AuthenticationSessionData(session_data))
        self.update_browser_from_session()

    def end_current_session(self):
        """
        Destroy the current session, and resume the previous one, if any.
        """
        self._logger.debug("Ending current session")
        if self._sessions_stack:
            self._sessions_stack.pop()
        self.update_browser_from_session()

    def update_session_from_browser(self):
        """
        Updtate our session from the browser cookies.

        We want to limit access to the actual session cookies, as their name
        in the browser may differ from how the value is named on our session
        representation, which is loosely based on that of RV itself.
        """
        self._logger.debug("Updating session cookies from browser")

        cookie_jar = self._view.page().networkAccessManager().cookieJar()

        # Here, the cookie jar is a dictionary of key/values
        cookies = SimpleCookie()

        for cookie in cookie_jar.allCookies():
            cookies.load(str(cookie.toRawForm()))

        encoded_cookies = _encode_cookies(cookies)
        content = {
            "session_expiration": get_saml_claims_expiration(encoded_cookies),
            "session_id": get_session_id(encoded_cookies),
            "user_id": get_user_name(encoded_cookies),
            "csrf_key": get_csrf_key(encoded_cookies),
            "csrf_value": get_csrf_token(encoded_cookies),
        }

        # To minimize handling, we also keep a snapshot of the browser cookies.
        # We do so for all of them, as some are used by the IdP and we do not
        # want to manage those. Their names may change from IdP version and
        # providers. We figure it is simpler to keep everything.

        # Here, we have a list of cookies in raw text form
        content["cookies"] = encoded_cookies

        self._session.merge_settings(content)

    def update_browser_from_session(self):
        """
        Update/reset the browser cookies with what we have.

        We keep in the session a snapshot of the cookies used in the login and
        renewal. These are persisted in the RV session. This function will
        be used when originally setting the browser for login using a saved
        session or when opening a connection to a new server.
        """
        self._logger.debug("Updating browser cookies from session")
        # pylint: disable=invalid-name
        QtNetwork = self._QtNetwork  # noqa

        qt_cookies = []
        if self._session is not None:
            parsed = _sanitize_http_proxy(self._session.http_proxy)
            if parsed.netloc:
                self._logger.debug(
                    "Using HTTP proxy: %s://%s", parsed.scheme, parsed.netloc
                )
                proxy = QtNetwork.QNetworkProxy(
                    QtNetwork.QNetworkProxy.HttpProxy,
                    parsed.hostname,
                    parsed.port,
                    parsed.username,
                    parsed.password,
                )
                QtNetwork.QNetworkProxy.setApplicationProxy(proxy)

            cookies = _decode_cookies(self._session.cookies)
            qt_cookies = QtNetwork.QNetworkCookie.parseCookies(
                cookies.output(header="")
            )

        self._view.page().networkAccessManager().cookieJar().setAllCookies(qt_cookies)

    def is_session_renewal_active(self):
        """
        Indicates if the automatic session renewal is used.

        :returns: True if it is, False otherwise.
        """
        return self._session_renewal_active

    def stop_session_renewal(self):
        """
        Stop automatic session renewal.

        This will be needed before opening a connection to a different server.
        We want to avoid confusion as to where the session is created and
        renewed.
        """
        self._logger.debug("Stopping automatic session renewal")

        self._session_renewal_active = False
        self._sso_renew_watchdog_timer.stop()
        self._sso_countdown_timer.stop()
        self._sso_renew_timer.stop()

    def start_sso_renewal(self):
        """
        Start the automated SSO session renewal.

        This will be done in the background, hopefully not impacting any
        ongoing process such as playback.
        """
        self._logger.debug("Starting automatic session renewal")

        self._sso_renew_watchdog_timer.stop()

        # We will need to cause an immediate renewal in order to get an
        # accurate knowledge of the session expiration. 0 is a special value
        # for QTimer intervals, so we use 1ms.
        interval = 1
        if self._session.session_expiration > time.time():
            interval = (
                (self._session.session_expiration - time.time())
                * self._sso_preemptive_renewal_threshold
                * 1000
            )

            # For debugging purposes
            # @TODO: Find a better way than to use this EV
            if "SHOTGUN_SSO_DEVELOPER_ENABLED" in os.environ:
                interval = SHOTGUN_SSO_RENEWAL_INTERVAL
        self._logger.debug("Setting session renewal interval to: %s seconds", interval)

        self._sso_countdown_timer.setInterval(interval)
        self._sso_countdown_timer.start()
        self._session_renewal_active = True

    def is_handling_event(self):
        """
        Called to know if an event is currently being handled.
        """
        return self._event_data is not None

    def handle_event(self, event_data):
        """
        Called to start the handling of an event.

        :param event_data: A dictionary with a 'event', 'host' and 'cookies' entries.
        """
        if not self.is_handling_event():
            self._event_data = event_data

            # At this point, we want to stop any background session renewal, as
            # it may impede with our new sesion login.
            self.stop_session_renewal()

            self.start_new_session(event_data)
        else:
            self._logger.error(
                "Calling handle_event while event %s is currently being handled",
                self._event_data["event"],
            )

    def resolve_event(self, end_session=False):
        """
        Called to return the results of the event.

        :param end_session: Boolean, indicating if the session should be ended.
        """
        if self.is_handling_event():
            if end_session:
                self.end_current_session()
            self._event_data = None
        else:
            self._logger.warn("Called resolve_event when no event is being handled.")

    def get_session_error(self):
        """
        Get the session error string.

        :returns: The error string of the last failed operation.
        """
        res = None
        if self._session and self._session.error:
            res = self._session.error
        return res

    ############################################################################
    #
    # QTimer callbacks
    #
    ############################################################################

    def on_schedule_sso_session_renewal(self):
        """
        Called to trigger the session renewal.

        The session renewal, via the off-screen QWebView, will be done at the
        next time the application event loop does not have any pending events.
        """
        self._logger.debug("Schedule SSO session renewal")
        self._sso_renew_timer.start()

    def on_renew_sso_session(self):
        """
        Called to renew the current SSO session.

        The renewal will be done via an off-screen QWebView. The intent is to
        benefit from the saved session cookies to automatically trigger the
        renewal without having the user having to enter any inputs.
        """
        self._logger.debug("Renew SSO session")
        self._sso_renew_watchdog_timer.start()

        # We do not update the page cookies, assuming that they have already
        # have been cleared/updated before.
        self._view.page().mainFrame().load(
            self._session.host + self.renew_path + "?product=%s" % self._session.product
        )

    def on_renew_sso_session_timeout(self):
        """
        Called when the SSO session renewal is taking too long to complete.

        The purpose of this callback is to stop the page loading.
        """
        self._logger.debug("Timeout awaiting session renewal")
        self._dialog.reject()

    ############################################################################
    #
    # Qt event handlers
    #
    ############################################################################

    def _polyfill(self):
        """
        Called by Qt when the Web Page has changed and before it is loaded.

        The purpose of this function is to inject JavaScript code in a page
        before any of its code is run. This gives us a way to modify the code's
        environment and define functions which would be required by that code.
        """
        frame = self._view.page().currentFrame()
        frame.evaluateJavaScript(FUNCTION_PROTOTYPE_BIND_POLYFILL)
        self._logger.debug(
            "Injected polyfill JavaScript code for Function.prototype.bind"
        )

    def on_load_finished(self, _succeeded):
        """
        Called by Qt when the Web Page has finished loading.

        The renewal process goes thru a number of redirects. We detect the
        end of the process by checking the page loaded, as we know where we
        expect to land in the end.

        At that point, we stop the process by sending the 'accept' event to
        the dialog. If the process is taking too long, we have a timer
        (_sso_renew_watchdog_timer) which will trigger and attempt to cleanup
        the process.

        :param succeeded: indicate the status of the load process. (not used)
        """
        url = self._view.page().mainFrame().url().toString().encode("utf-8")
        if (
            # This callback may be triggered outside the actual auth process
            # like when we clear the page to use the "about:blank".
            # or after there has been a prior error. So we ensure that we
            # update our session and accept only when we really have to.
            self._session is not None
            and self._event_data is not None
            and url.startswith(self._session.host + self.landing_path)
        ):
            self.update_session_from_browser()
            if self._session_renewal_active:
                self.start_sso_renewal()

            self._dialog.accept()

    def on_authentication_required(self, _reply, authenticator):
        """
        Called when authentication is required to get to a web page.

        This method is required to support NTLM/Kerberos on a Windows machine,
        of if there is a SSO Desktop integration plugin.

        :param reply: Qt reply object. Not used.
        :param authenticator: Qt authenticator object.
        """
        # We take for granted that if we are on Windows, proper NTLM negociation
        # is possible between the machine and the IdP. For other platforms, we
        # pop an authentication dialog.
        if sys.platform != "win32" and UsernamePasswordDialog is not None:
            message = (
                "<p>Your company has configured Single Sign-On (SSO) for the Shotgun site %s"
                "<p>Please authenticate with your computer login and password to log into Shotgun."
                "<p>"
            )
            auth_dialog = UsernamePasswordDialog(message=message % self._session.host)
            if auth_dialog.exec_():
                authenticator.setUser(auth_dialog.username)
                authenticator.setPassword(auth_dialog.password)
            else:
                self._logger.debug("User prompted for username/password but canceled")
        else:
            if UsernamePasswordDialog is None:
                self._logger.debug(
                    "Unable to prompt user for username/password, due to missing username_password_dialog module"
                )
            # Setting the user to an empty string tells the QAuthenticator to
            # negotiate the authentication with the user's credentials.
            authenticator.setUser("")

    ############################################################################
    #
    # Events handlers
    #
    ############################################################################

    def on_sso_login_attempt(self, event_data=None, use_watchdog=False):
        """
        Called to attempt a login process with user interaction.

        The user will be presented with the appropriate web pages from their
        IdP in order to log on to Shotgun.

        :returns: 1 if successful, 0 otherwise.
        """
        self._logger.debug("Web login attempt")
        # pylint: disable=invalid-name
        QtCore = self._QtCore  # noqa

        if event_data is not None:
            self.handle_event(event_data)

        if use_watchdog:
            self._logger.debug("Starting watchdog")
            self._sso_renew_watchdog_timer.start()

        # If we do have session cookies, let's attempt a session renewal
        # without presenting any GUI.
        if self._session.cookies:
            self._logger.debug("Attempting a GUI-less renewal")
            loop = QtCore.QEventLoop(self._dialog)
            self._dialog.finished.connect(loop.exit)
            self.on_renew_sso_session()
            status = loop.exec_()
            self._login_status = self._login_status or status
            return self._login_status

        self._view.show()
        self._view.raise_()

        # We append the product code to the GET request.
        self._view.page().mainFrame().load(
            self._session.host + self.renew_path + "?product=%s" % self._session.product
        )

        self._dialog.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        status = self._dialog.exec_()
        self._login_status = self._login_status or status
        return self._login_status

    def on_dialog_closed(self, result):
        """
        Called whenever the dialog is dismissed.

        This can be the result of a callback, a timeout or user interaction.

        :param result: Qt result following the closing of the dialog.
                       QtGui.QDialog.Accepted or QtGui.QDialog.Rejected
        """
        self._logger.debug("SSO dialog closed")
        # pylint: disable=invalid-name
        QtGui = self._QtGui  # noqa

        if self.is_handling_event():
            if result == QtGui.QDialog.Rejected and self._session.cookies != "":
                # We got here because of a timeout attempting a GUI-less login.
                # Let's clear the cookies, and force the use of the GUI.
                self._session.cookies = ""
                # Let's have another go, without any cookies this time !
                # This will force the GUI to be shown to the user.
                self._logger.debug(
                    "Unable to login/renew claims automaticall, presenting GUI to user"
                )
                status = self.on_sso_login_attempt()
                self._login_status = self._login_status or status
            else:
                self.resolve_event()
        else:
            # Should we get a rejected dialog, then we have had a timeout.
            if result == QtGui.QDialog.Rejected:
                # @FIXME: Figure out exactly what to do when we have a timeout.
                self._logger.warn(
                    "Our QDialog got canceled outside of an event handling"
                )

        # Clear the web page
        self._view.page().mainFrame().load("about:blank")
