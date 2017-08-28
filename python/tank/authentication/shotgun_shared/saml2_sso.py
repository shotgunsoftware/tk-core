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
Module to support SSO login via a web browser and automated session renewal.

This module, in conjunction with the slmodule, handles authentication on
SSO enabled Shotgun websites. When we are in a session connected via SSO, we
also handle automatic (and headless) renewal of the session.
"""

import base64
from Cookie import SimpleCookie
import json
import logging
import os
import time
import urllib

from .authentication_session_data import AuthenticationSessionData
from ..ui.qt_abstraction import QtCore, QtNetwork, QtGui, QtWebKit
from ... import LogManager

log = LogManager.get_logger(__name__)


# Error messages for events. . Also defined in slmodule/slutils.mu
# @FIXME: Should import these from slmodule
HTTP_CANT_CONNECT_TO_SHOTGUN = "Cannot Connect To Shotgun site."
HTTP_AUTHENTICATE_REQUIRED = "Valid credentials are required."
HTTP_AUTHENTICATE_SSO_NOT_UPPORTED = "SSO not supported or enabled on that site."
HTTP_CANT_AUTHENTICATE_SSO_TIMEOUT = "Time out attempting to authenticate to SSO service."
HTTP_CANT_AUTHENTICATE_SSO_NO_ACCESS = "You have not been granted access to the Shotgun site."

# Paths for bootstrap the login/renewal process.
URL_SAML_RENEW_PATH = "/saml/saml_renew"
URL_SAML_RENEW_LANDING_PATH = "/saml/saml_renew_landing"

# Old login path, which is not used for SSO.
URL_LOGIN_PATH = "/user/login"

# Timer related values.
# @TODO: parametrize these and add environment variable overload.
WATCHDOG_TIMEOUT_MS = 5000
PREEMPTIVE_RENEWAL_THRESHOLD = 0.9
SHOTGUN_SSO_RENEWAL_INTERVAL = 5000


class Saml2SssoError(Exception):
    """
    Top level exception for all saml2_sso level runtime errors
    """


class Saml2SssoMultiSessionNotSupportedError(Saml2SssoError):
    """
    Exception that indicates the cookies contains sets of tokens from mutliple users.
    """


class Saml2SssoMissingQtModule(Saml2SssoError):
    """
    Exception that indicates that a required Qt component is missing.
    """


class Saml2SssoMissingQtNetwork(Saml2SssoMissingQtModule):
    """
    Exception that indicates that the QtNetwork component is missing.
    """


class Saml2SssoMissingQtWebKit(Saml2SssoMissingQtModule):
    """
    Exception that indicates that the QtWebKit component is missing.
    """


class Saml2Sso(object):
    """Performs Shotgun SSO login and pre-emptive renewal."""

    def __init__(self, window_title="SSO"):
        """Initialize the RV mode."""
        log.debug("==- __init__")

        if QtNetwork is None:
            raise Saml2SssoMissingQtNetwork("The QtNetwork module is unavailable")

        if QtWebKit is None:
            raise Saml2SssoMissingQtWebKit("The QtWebKit module is unavailable")

        self._event_data = None
        self._sessions_stack = []
        self._session_renewal_active = False

        self._dialog = QtGui.QDialog()
        self._dialog.setWindowTitle(window_title)
        self._dialog.finished.connect(self.on_dialog_closed)

        self._view = QtWebKit.QWebView(self._dialog)
        self._view.page().networkAccessManager().finished.connect(self.on_http_response_finished)
        self._view.loadFinished.connect(self.on_load_finished)

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
        css_style = base64.b64encode("div.browser_not_approved { display: none !important; }")
        self._view.settings().setUserStyleSheetUrl("data:text/css;charset=utf-8;base64," + css_style)

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
        self._sso_renew_watchdog_timer.timeout.connect(self.on_renew_sso_session_timeout)

        # We need a way to trace the current status of our login process.
        self._login_status = 0

        # For debugging purposes
        # @TODO: Find a better way than to use the log level
        if log.level == logging.DEBUG or "SHOTGUN_SSO_DEVELOPER_ENABLED" in os.environ:
            log.debug("==- Using developer mode. Disabling strict SSL mode, enabling developer tools and local storage.")
            # Disable SSL validation, useful when using a VM or a test site.
            config = QtNetwork.QSslConfiguration.defaultConfiguration()
            config.setPeerVerifyMode(QtNetwork.QSslSocket.VerifyNone)
            QtNetwork.QSslConfiguration.setDefaultConfiguration(config)

            # Adds the Developer Tools option when right-clicking
            QtWebKit.QWebSettings.globalSettings().setAttribute(
                QtWebKit.QWebSettings.WebAttribute.DeveloperExtrasEnabled,
                True
            )
            QtWebKit.QWebSettings.globalSettings().setAttribute(
                QtWebKit.QWebSettings.WebAttribute.LocalStorageEnabled,
                True
            )

    def __del__(self):
        """Destructor."""
        log.debug("==- __del__")

    @property
    def _session(self):
        """
        String RO property.

        Returns the current session, if any. The session provides information
        on the current context (host, user ID, etc.)
        """
        return self._sessions_stack[-1] if len(self._sessions_stack) > 0 else None

    def start_new_session(self, session_data):
        """
        Create a new session, based on the data provided.
        """
        log.debug("==- start_new_session")
        self._sessions_stack.append(AuthenticationSessionData(session_data))
        self.update_browser_from_session()

    def end_current_session(self):
        """
        Destroy the current session, and resume the previous one, if any.
        """
        log.debug("==- end_current_session")
        if len(self._sessions_stack) > 0:
            self._sessions_stack.pop()
        self.update_browser_from_session()

    def update_session_from_browser(self):
        """
        Updtate our session from the browser cookies.

        We want to limit access to the actual session cookies, as their name
        in the browser may differ from how the value is named on our session
        representation, which is loosely based on that of RV itself.
        """
        log.debug("==- update_session_from_browser")

        cookie_jar = self._view.page().networkAccessManager().cookieJar()

        # Here, the cookie jar is a dictionary of key/values
        cookies = SimpleCookie()

        for cookie in cookie_jar.allCookies():
            cookies.load(str(cookie.toRawForm()))

        encoded_cookies = _encode_cookies(cookies)
        content = {
            "session_expiration": get_saml_claims_expiration(encoded_cookies),
            "session_id": get_session_id(encoded_cookies),
            "user_id": get_saml_user_name(encoded_cookies),
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
        log.debug("==- update_browser_from_session")

        qt_cookies = []
        if self._session is not None:
            cookies = _decode_cookies(self._session.cookies)
            qt_cookies = QtNetwork.QNetworkCookie.parseCookies(cookies.output(header=""))

        self._view.page().networkAccessManager().cookieJar().setAllCookies(qt_cookies)

    def stop_session_renewal(self):
        """
        Stop automatic session renewal.

        This will be needed before opening a connection to a different server.
        We want to avoid confusion as to where the session is created and
        renewed.
        """
        log.debug("==- stop_session_renewal")

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
        log.debug("==- start_sso_renewal")

        self._sso_renew_watchdog_timer.stop()

        # We will need to cause an immediate renewal in order to get an
        # accurate knowledge of the session expiration. 0 is a special value
        # for QTimer intervals, so we use 1ms.
        interval = 1
        if self._session.session_expiration > time.time():
            interval = (self._session.session_expiration - time.time()) * self._sso_preemptive_renewal_threshold * 1000

            # For debugging purposes
            # @TODO: Find a better way than to use this EV
            if "SHOTGUN_SSO_DEVELOPER_ENABLED" in os.environ:
                interval = SHOTGUN_SSO_RENEWAL_INTERVAL
        log.debug("==- start_sso_renewal: interval: %s" % interval)

        self._sso_countdown_timer.setInterval(interval)
        self._sso_countdown_timer.start()
        self._session_renewal_active = True

    def on_http_response_finished(self, reply):
        """
        This callbaback is triggered after every page load in the QWebView.
        """
        # log.debug("==- on_http_response_finished")

        error = reply.error()
        url = reply.url().toString().encode("utf-8")
        session = AuthenticationSessionData() if self._session is None else self._session

        if (
            error is not QtNetwork.QNetworkReply.NetworkError.NoError and
            error is not QtNetwork.QNetworkReply.NetworkError.OperationCanceledError
        ):
            if error is QtNetwork.QNetworkReply.NetworkError.HostNotFoundError:
                session.error = HTTP_CANT_CONNECT_TO_SHOTGUN
            elif error is QtNetwork.QNetworkReply.NetworkError.ContentNotFoundError:
                if url.startswith(session.host + URL_SAML_RENEW_PATH):
                    # This is likely because the subdomain is not valid.
                    # e.g. https://foobar.shotgunstudio.com
                    # Here the domain (shotgunstudio.com) is valid, but not
                    # foobar.
                    session.error = HTTP_CANT_CONNECT_TO_SHOTGUN
                else:
                    # We silently ignore content not found otherwise.
                    pass
            elif error is QtNetwork.QNetworkReply.NetworkError.UnknownContentError:
                # This means that the site does not support SSO or that
                # it is not enabled.
                session.error = HTTP_AUTHENTICATE_SSO_NOT_UPPORTED
            elif error is QtNetwork.QNetworkReply.NetworkError.ContentOperationNotPermittedError:
                # This means that the SSO login worked, but that the user does
                # have access to the site.
                session.error = HTTP_CANT_AUTHENTICATE_SSO_NO_ACCESS
            elif error is QtNetwork.QNetworkReply.NetworkError.AuthenticationRequiredError:
                # This means that the user entered incorrect credentials.
                if url.startswith(session.host):
                    session.error = HTTP_AUTHENTICATE_REQUIRED
                else:
                    # If we are not on our site, we are on the Identity Provider (IdP) portal site.
                    # We let it deal with the error.
                    # Reset the error to None to disregard the error.
                    session.error = None
            else:
                session.error = reply.attribute(QtNetwork.QNetworkRequest.HttpReasonPhraseAttribute)
        elif url.startswith(session.host + URL_LOGIN_PATH):
            # If we are being redirected to the login page, then SSO is not
            # enabled on that site.
            session.error = HTTP_AUTHENTICATE_SSO_NOT_UPPORTED

        if session.error:
            # If there are any errors, we exit by force-closing the dialog.
            log.error("==- on_http_response_finished: %s - %s - %s" % (url, error, session.error))
            self._dialog.reject()

    def is_handling_event(self):
        """
        Called to know if an event is currently being handled.
        """
        # log.debug("==- is_handling_event")
        return self._event_data is not None

    def handle_event(self, event_data):
        """
        Called to start the handling of an event.
        """
        log.debug("==- handle_event")

        if not self.is_handling_event():
            self._event_data = event_data

            # At this point, we want to stop any background session renewal, as
            # it may impede with our new sesion login.
            self.stop_session_renewal()

            self.start_new_session(event_data)
        else:
            log.error("Calling handle_event while event %s is currently being handled" % self._event_data["event"])

    def resolve_event(self, end_session=False):
        """
        Called to return the results of the event.
        """
        log.debug("==- resolve_event")

        if self.is_handling_event():
            # rvc.sendInternalEvent(self._event_data["event"], self._session.assembleSession())
            if end_session:
                self.end_current_session()
            self._event_data = None
        else:
            log.error("Called resolve_event when no event is being handled.")

    def get_session_data(self):
        """Returns the relevant session data for the toolkit."""
        return (
            self._session.host,
            self._session.user_id,
            self._session.session_id,
            self._session.cookies
        )

    def get_session_error(self):
        """Returns the the error string of the last failed operation."""
        res = None
        if self._session and len(self._session.error) > 0:
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
        log.debug("==- on_schedule_sso_session_renewal")

        self._sso_renew_timer.start()

    def on_renew_sso_session(self):
        """
        Called to renew the current SSO session.

        The renewal will be done via an off-screen QWebView. The intent is to
        benefit from the saved session cookies to automatically trigger the
        renewal without having the user having to enter any inputs.
        """
        log.debug("==- on_renew_sso_session")

        self._sso_renew_watchdog_timer.start()

        # We do not update the page cookies, assuming that they have already
        # have been cleared/updated before.
        self._view.page().mainFrame().load(self._session.host + URL_SAML_RENEW_PATH)

    def on_renew_sso_session_timeout(self):
        """
        Called when the SSO session renewal is taking too long to complete.

        The purpose of this callback is to stop the page loading.
        """
        log.debug("==- on_renew_sso_session_timeout")
        # @FIXME: Not sure this is the proper thing to do
        # self._view.page().triggerAction(QtWebKit.QWebPage.Stop)
        self._dialog.reject()

    ############################################################################
    #
    # Qt event handlers
    #
    ############################################################################

    def on_load_finished(self, succeeded):
        """
        Called by Qt when the Web Page has finished loading.

        The renewal process goes thru a number of redirects. We detect the
        end of the process by checking the page loaded, as we know where we
        expect to land in the end.

        At that point, we stop the process by sending the 'accept' event to
        the dialog. If the process is taking too long, we have a timer
        (_sso_renew_watchdog_timer) which will trigger and attempt to cleanup
        the process.
        """
        # log.debug("==- on_load_finished")

        url = self._view.page().mainFrame().url().toString().encode("utf-8")
        if (
                self._session is not None and
                url.startswith(self._session.host + URL_SAML_RENEW_LANDING_PATH)
        ):
            self.update_session_from_browser()
            if self._session_renewal_active:
                self.start_sso_renewal()

            self._dialog.accept()

        if not succeeded and url != "":
            log.error("Loading of page \"%s\" generated an error." % url)
            # @FIXME: Figure out proper way of handling error.

    ############################################################################
    #
    # Mu events handlers
    #
    ############################################################################

    def on_sso_login_attempt(self, event_data=None, use_watchdog=False):
        """
        Called to attempt a login process with user interaction.

        The user will be presented with the appropriate web pages from their
        IdP in order to log on to Shotgun.
        """
        log.debug("==- on_sso_login_attempt")

        if event_data is not None:
            self.handle_event(event_data)

        if use_watchdog:
            log.debug("==- on_sso_login_attempt: Starting watchdog")
            self._sso_renew_watchdog_timer.start()

        # If we do have session cookies, let's attempt a session renewal
        # without presenting any GUI.
        if self._session.cookies:
            loop = QtCore.QEventLoop(self._dialog)
            self._dialog.finished.connect(loop.exit)
            self.on_renew_sso_session()
            status = loop.exec_()
            self._login_status = self._login_status or status
            return self._login_status

        else:
            self._view.show()
            self._view.raise_()

            # We append the product code to the GET request.
            self._view.page().mainFrame().load(
                self._session.host + URL_SAML_RENEW_PATH + "?product=%s" % self._session.product
            )

            self._dialog.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
            status = self._dialog.exec_()
            self._login_status = self._login_status or status
            return self._login_status

    def on_sso_login_cancel(self, event):
        """
        Called to cancel an ongoing login attempt.
        """
        log.debug("==- on_sso_login_cancel")

        # We only need to cancel if there is login attempt currently being made.
        if self.is_handling_event():
            self.stop_session_renewal()
            self.resolve_event(end_session=True)
        self._dialog.accept()

    def on_dialog_closed(self, result):
        """
        Called whenever the dialog is dismissed.

        This can be the result of a callback, a timeout or user interaction.
        """
        log.debug("==- on_dialog_closed")

        if self.is_handling_event():
            if result == QtGui.QDialog.Rejected and self._session.cookies != "":
                # We got here because of a timeout attempting a GUI-less login.
                # Let's clear the cookies, and force the use of the GUI.
                self._session.cookies = ""
                # Let's have another go, without any cookies this time !
                # This will force the GUI to be shown to the user.
                log.debug("==- Unable to login/renew claims automaticall, presenting GUI to user")
                status = self.on_sso_login_attempt()
                self._login_status = self._login_status or status
            else:
                # end_session = result == QtGui.QDialog.Rejected
                # self.resolve_event(end_session=end_session)
                log.debug("==- Resolving event")
                self.resolve_event()
        else:
            # Should we get a rejected dialog, then we have had a timeout.
            if result == QtGui.QDialog.Rejected:
                # @FIXME: Figure out exactly what to do when we have a timeout.
                log.warn("Our QDialog got canceled outside of an event handling...")

        # Clear the web page
        self._view.page().mainFrame().load("about:blank")

    def on_sso_enable_renewal(self, event):
        """
        Called when enabling automatic SSO session renewal.

        A new session will be created if there is not already a current one.
        This will be in the case of the automatic (and successful)
        authentication at the startup of the application.

        """
        log.debug("==- on_sso_enable_renewal")

        contents = json.loads(event.contents())

        if self._session is None:
            self.start_new_session({
                "host": contents["params"]["site_url"],
                "cookies": contents["params"]["cookies"]
            })
        self.start_sso_renewal()

    def on_sso_disable_renewal(self, event):
        """
        Called to disable automatic session renewal.

        This will be required when switching to a new connection (where the new
        site may not using SSO) or at the close of the application.
        """
        log.debug("==- on_sso_disable_renewal")

        self.stop_session_renewal()

################################################################################
#
# functions
#
################################################################################


def _decode_cookies(encoded_cookies):
    """
    Extract the cookies from a base64 encoded string.

    :param encoded_cookies: An encoded string representing the cookie jar.

    :returns: A SimpleCookie containing all the cookies.
    """
    cookies = SimpleCookie()
    if encoded_cookies:
        try:
            decoded_cookies = base64.b64decode(encoded_cookies)
            cookies.load(decoded_cookies)
        except TypeError, e:
            log.error("Unable to decode the cookies: %s" % e.message)
    return cookies


def _encode_cookies(cookies):
    """
    Extract the cookies from a base64 encoded string.

    :param cookies: A Cookie.SimpleCookie instance representing the cookie jar.

    :returns: An encoded string representing the cookie jar.
    """
    encoded_cookies = base64.b64encode(cookies.output())
    return encoded_cookies


def _get_shotgun_user_id(cookies):
    """
    Returns the id of the user in the shotgun instance, based on the cookies.

    :param cookies: A Cookie.SimpleCookie instance representing the cookie jar.

    :returns: A string user id value, or None.
    """
    user_id = None
    user_domain = None
    for cookie in cookies:
        # Shotgun appends the unique numerical ID of the user to the cookie name:
        # ex: shotgun_sso_session_userid_u78
        if cookie.startswith("shotgun_sso_session_userid_u"):
            if user_id is not None:
                # Should we find multiple cookies with the same prefix, it means
                # that we are using cookies from a multi-session environment. We
                # have no way to identify the proper user id in the lot.
                message = "The cookies for this user seem to come from two different shotgun sites: '%s' and '%s'"
                raise Saml2SssoMultiSessionNotSupportedError(message % (user_domain, cookies[cookie]['domain']))
            user_id = cookie[28:]
            user_domain = cookies[cookie]['domain']
    return user_id


def _get_cookie_from_prefix(encoded_cookies, cookie_prefix):
    """
    Returns a cookie value based on a prefix to which we will append the user id.

    :param encoded_cookies: An encoded string representing the cookie jar.
    :param cookie_prefix: The prefix of the cookie name.

    :returns: A string of the cookie value, or None.
    """
    value = None
    cookies = _decode_cookies(encoded_cookies)
    key = "%s%s" % (cookie_prefix, _get_shotgun_user_id(cookies))
    if key in cookies:
        value = cookies[key].value
    return value


def is_sso_enabled(encoded_cookies):
    """
    Indicate if SSO is being used from the Shotgun cookies.

    :param encoded_cookies: An encoded string representing the cookie jar.

    :returns: True or False
    """
    cookies = _decode_cookies(encoded_cookies)
    return _get_shotgun_user_id(cookies) is not None


def get_saml_claims_expiration(encoded_cookies):
    """
    Obtain the expiration time of the saml claims from the Shotgun cookies.

    :param encoded_cookies: An encoded string representing the cookie jar.

    :returns: An int with the time in seconds since January 1st 1970 UTC, or None
    """
    # Shotgun appends the unique numerical ID of the user to the cookie name:
    # ex: shotgun_sso_session_expiration_u78
    saml_claims_expiration = _get_cookie_from_prefix(encoded_cookies, "shotgun_sso_session_expiration_u")
    if saml_claims_expiration is not None:
        saml_claims_expiration = int(saml_claims_expiration)
    return saml_claims_expiration


def get_saml_user_name(encoded_cookies):
    """
    Obtain the saml user name from the Shotgun cookies.

    :param encoded_cookies: An encoded string representing the cookie jar.

    :returns: A string with the user name, or None
    """
    # Shotgun appends the unique numerical ID of the user to the cookie name:
    # ex: shotgun_sso_session_userid_u78
    user_name = _get_cookie_from_prefix(encoded_cookies, "shotgun_sso_session_userid_u")
    if user_name is not None:
        user_name = urllib.unquote(user_name)
    return user_name


def get_session_id(encoded_cookies):
    """
    Obtain the session id from the Shotgun cookies.

    :param encoded_cookies: An encoded string representing the cookie jar.

    :returns: A string with the session id, or None
    """
    session_id = None
    cookies = _decode_cookies(encoded_cookies)
    key = "_session_id"
    if key in cookies:
        session_id = cookies[key].value
    return session_id


def get_csrf_token(encoded_cookies):
    """
    Obtain the csrf token from the Shotgun cookies.

    :param encoded_cookies: An encoded string representing the cookie jar.

    :returns: A string with the csrf token, or None
    """
    # Shotgun appends the unique numerical ID of the user to the cookie name:
    # ex: csrf_token_u78
    return _get_cookie_from_prefix(encoded_cookies, "csrf_token_u")


def get_csrf_key(encoded_cookies):
    """
    Obtain the csrf token name from the Shotgun cookies.

    :param encoded_cookies: An encoded string representing the cookie jar.

    :returns: A string with the csrf token name
    """
    cookies = _decode_cookies(encoded_cookies)
    # Shotgun appends the unique numerical ID of the user to the cookie name:
    # ex: csrf_token_u78
    return "csrf_token_u%s" % _get_shotgun_user_id(cookies)


################################################################################
#
# logging
#
################################################################################
