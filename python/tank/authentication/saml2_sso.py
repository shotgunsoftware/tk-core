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
import json
import logging
import os
import time

from .authentication_session_data import AuthenticationSessionData
from .ui.qt_abstraction import QtCore, QtNetwork, QtGui, QtWebKit
from .. import LogManager

log = LogManager.get_logger(__name__)


# Error messages for events. . Also defined in slmodule/slutils.mu
# @FIXME: Should import these from slmodule
HTTP_CANT_CONNECT_TO_SHOTGUN = "Cannot Connect To Shotgun"
HTTP_AUTHENTICATE_SSO_NOT_UPPORTED = "SSO not supported or enabled"
HTTP_CANT_AUTHENTICATE_SSO_TIMEOUT = "Time out attempting to authenticate to SSO service"
HTTP_CANT_AUTHENTICATE_SSO_NO_ACCESS = "You have not been granted access to the Shotgun site"

# Paths for bootstrap the login/renewal process.
URL_SAML_RENEW_PATH = "/saml/saml_renew"
URL_SAML_RENEW_LANDING_PATH = "/saml/saml_renew_landing"

# Old login path, which is not used for SSO.
URL_LOGIN_PATH = "/user/login"


class Saml2Sso(object):
    """Performs Shotgun SSO login and pre-emptive renewal."""

    def __init__(self, window_title="SSO"):
        """Initialize the RV mode."""
        log.debug("==- __init__")

        self._event_data = None
        self._sessions_stack = []
        self._session_renewal_active = False

        self._dialog = QtGui.QDialog()
        self._dialog.setWindowTitle(window_title)
        self._dialog.finished.connect(self.on_dialog_closed)

        self._view = QtWebKit.QWebView(self._dialog)
        self._view.page().networkAccessManager().finished.connect(self.on_http_response_finished)

        # Purposely disable the 'Reload' contextual menu, as it should not be
        # used for SSO. Reloading the page confuses the server.
        self._view.page().action(QtWebKit.QWebPage.Reload).setVisible(False)

        # Ensure that the background color is not controlled by the login page.
        self._view.setStyleSheet("background-color:white;")
        self._view.loadFinished.connect(self.on_load_finished)

        # Threshold percentage of the SSO session duration, at which
        # time the pre-emptive renewal operation should be started.
        # @TODO: Make threshold parameter configurable.
        self._sso_preemptive_renewal_threshold = 0.9

        # We use the _sso_countdown_timer so that it fires once. Its purpose
        # is to start the other _sso_renew_timer. It fires once at an interval
        # of '0', which means 'whenever there are no event waiting in the
        # queue'. The intent is that it will execute the actual (and costly)
        # renewal at a time when the main event loop is readily available.
        #
        # The _sso_countdown_timer will be re-started in on_renew_sso_session.
        # Thus re-starting the chain of reneal events.
        self._sso_countdown_timer = QtCore.QTimer()
        self._sso_countdown_timer.setSingleShot(True)
        self._sso_countdown_timer.timeout.connect(self.on_schedule_sso_session_renewal)

        self._sso_renew_timer = QtCore.QTimer()
        self._sso_renew_timer.setInterval(0)
        self._sso_renew_timer.setSingleShot(True)
        self._sso_renew_timer.timeout.connect(self.on_renew_sso_session)

        # Watchdog timer to detect abnormal conditions during SSO
        # session renewal.
        # If timeout occurs, then the renewal is considered to have
        # failed, therefore the operation is aborted and recovery
        # by interactive authentication is initiated.
        # @TODO: Make watchdog timer duration configurable.
        self._sso_renew_watchdog_timeout_ms = 5000
        self._sso_renew_watchdog_timer = QtCore.QTimer()
        self._sso_renew_watchdog_timer.setInterval(self._sso_renew_watchdog_timeout_ms)
        self._sso_renew_watchdog_timer.setSingleShot(True)
        self._sso_renew_watchdog_timer.timeout.connect(self.on_renew_sso_session_timeout)

        # For debugging purposes
        # @TODO: Find a better way than to use the log level
        if log.level == logging.DEBUG or "SGTK_SHOTGUN_USING_VM" in os.environ:
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

            # # Automatically popup the inspector.
            # self._inspector = QtWebKit.QWebInspector()
            # self._inspector.setPage(self._view.page())
            # self._inspector.show()

    # def __del__(self):
    #     """TBD."""
    #     # log.debug("==- __del__")
    #     print "==- __del__"
    #     self.stop_session_renewal()
    #     # if log.level == logging.DEBUG or "SGTK_SHOTGUN_USING_VM" in os.environ:
    #     #     self._inspector.close()

    @property
    def _session(self):
        """String RO property."""
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
        cookies = {}

        for cookie in cookie_jar.allCookies():
            cookies[str(cookie.name()).decode("utf-8")] = str(cookie.value())

        content = {}
        for key, value in cookies.iteritems():
            if key.startswith("shotgun_sso_session_expiration_u"):
                content["session_expiration"] = int(value)
            if key == "_session_id":
                content["session_id"] = value
            if key.startswith("shotgun_sso_session_userid_u"):
                content["user_id"] = value
            if key.startswith("csrf_token_u"):
                content["csrf_key"] = key
                content["csrf_value"] = value

        # To minimize handling, we also keep a snapshot of the browser cookies.
        # We do so for all of them, as some are used by the IdP and we do not
        # want to manage those. Their names may change from IdP version and
        # providers. We figure it is simpler to keep everything.

        # Here, we have a list of cookies in raw text form
        raw_cookies = []
        for cookie in cookie_jar.allCookies():
            raw_cookies.append(str(cookie.toRawForm()))

        content["cookies"] = _encode_cookies(raw_cookies)

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
            qt_cookies = [QtNetwork.QNetworkCookie.parseCookies(cookie)[0] for cookie in cookies]

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
        print "==- start_sso_renewal"

        self._sso_renew_watchdog_timer.stop()

        # We will need to cause an immediate renewal in order to get an
        # accurate knowledge of the session expiration. 0 is a special value
        # for QTimer intervals, so we use 1ms.
        interval = 1
        if self._session.session_expiration > time.time():
            interval = (self._session.session_expiration - time.time()) * self._sso_preemptive_renewal_threshold * 1000

            # For debugging purposes
            # @TODO: Find a better way than to use this EV
            if "RV_SHOTGUN_USING_VM" in os.environ:
                interval = 5000
        log.debug("==- start_sso_renewal: interval: %s" % interval)
        print "==- start_sso_renewal: interval: %s" % interval

        self._sso_countdown_timer.setInterval(interval)
        self._sso_countdown_timer.start()
        self._session_renewal_active = True

    def on_http_response_finished(self, reply):
        """on_http_response_finished."""
        log.debug("==- on_http_response_finished")

        error = reply.error()
        url = reply.url().toString()
        log.debug("==- on_http_response_finished: %s" % url)
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
                    pass
            elif error is QtNetwork.QNetworkReply.NetworkError.UnknownContentError:
                # This means that the site does not support SSO or that
                # it is not enabled.
                session.error = HTTP_AUTHENTICATE_SSO_NOT_UPPORTED
            elif error is QtNetwork.QNetworkReply.NetworkError.ContentOperationNotPermittedError:
                # This means that the SSO login worked, but that the user does
                # have access to the site.
                session.error = HTTP_CANT_AUTHENTICATE_SSO_NO_ACCESS
            else:
                session.error = reply.attribute(QtNetwork.QNetworkRequest.HttpReasonPhraseAttribute)
                log.error("==- on_http_response_finished: %s - %s" % (reply.url(), reply.error()))
        elif url.startswith(session.host + URL_LOGIN_PATH):
            # If we are being redirected to the login page, then SSO is not
            # enabled on that site.
            session.error = HTTP_AUTHENTICATE_SSO_NOT_UPPORTED

        if session.error:
            # If there are any errors, we exit by force-closing the dialog.
            print "OHHH WELL: %s" % session.error
            self._dialog.accept()

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
            self._session.cookies,
            self._session.session_expiration
        )

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
        print "LOADING PAGE: %s" % self._session.host + URL_SAML_RENEW_PATH
        self._view.page().mainFrame().load(self._session.host + URL_SAML_RENEW_PATH)

    def on_renew_sso_session_timeout(self):
        """
        Called when the SSO session renewal is taking too long to complete.

        The purpose of this callback is to stop the page loading.
        """
        log.debug("==- on_renew_sso_session_timeout")
        print "==- on_renew_sso_session_timeout"
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

        url = self._view.page().mainFrame().url().toString()
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

    def on_sso_login_attempt(self, event_data=None):
        """
        Called to attempt a login process with user interaction.

        The user will be presented with the appropriate web pages from their
        IdP in order to log on to Shotgun.
        """
        log.debug("==- on_sso_login_attempt")

        if event_data is not None:
            self.handle_event(event_data)

        # If we do have session cookies, let's attempt a session renewal
        # without presenting any GUI.
        if self._session.cookies:
            loop = QtCore.QEventLoop()
            self._dialog.finished.connect(loop.exit)
            self.on_renew_sso_session()
            res = loop.exec_()
            return res

        else:
            self._view.show()
            self._view.raise_()

            # We append the product code to the GET request.
            self._view.page().mainFrame().load(
                self._session.host + URL_SAML_RENEW_PATH + "?product=%s" % self._session.product
            )

            self._dialog.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
            return self._dialog.exec_()

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
                self.on_sso_login_attempt()
            else:
                end_session = result == QtGui.QDialog.Rejected
                self.resolve_event(end_session=end_session)
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


def _decode_cookies(rv_cookies):
    sg_cookies = []
    if rv_cookies:
        sg_cookies = json.loads(base64.b64decode(rv_cookies))
        sg_cookies = [cookie.encode("utf-8") for cookie in sg_cookies]
    return sg_cookies


def _encode_cookies(sg_cookies):
    rv_cookies = base64.b64encode(json.dumps(sg_cookies))
    return rv_cookies


################################################################################
#
# logging
#
################################################################################
