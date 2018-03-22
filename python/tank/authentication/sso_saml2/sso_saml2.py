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
Integration with Shotgun API.
"""

from .core import (  # noqa
    SsoSaml2Core,
)

from .utils import (  # noqa
    is_sso_enabled_on_site,
    set_logger_parent,
)


class SsoSaml2(object):
    """
    This class provides a minimal interface to support SSO authentication.
    """

    def __init__(self, window_title=None, qt_modules=None):
        """
        Create a SSO login dialog, using a Web-browser like environment.

        :param window_title: Title to use for the window.
        :param qt_modules:   a dictionnary of required Qt modules.
                             For Qt4/PySide, we require modules QtCore, QtGui, QtNetwork and QtWebKit

        :returns: The SsoSaml2 oject.
        """
        window_title = window_title or "SSO"
        qt_modules = qt_modules or {}
        self._core = SsoSaml2Core(window_title=window_title, qt_modules=qt_modules)

    def login_attempt(self, host, cookies=None, product=None, http_proxy=None, use_watchdog=False):
        """
        Called to attempt a login process.

        If valid cookies are proviced, an initial attempt will be made to log in
        without showing GUI to the user.

        If this fails, or there are no cookies, the user will be prompted for
        their credentials.

        :param host:         URL of the Shotgun server.
        :param cookies:      String of encoded cookies.
        :param product:      String describing the application attempting to login.
                             This string will appear in the Shotgun server logs.
        :param http_proxy:   URL of the proxy.
        :param use_watchdog:

        :returns: True if the login was successful.
        """
        product = product or "Undefined"
        success = self._core.on_sso_login_attempt({
            "host": host,
            "http_proxy": http_proxy,
            "cookies": cookies,
            "product": product,
        }, use_watchdog)
        return success == 1

    def is_automatic_claims_renewal_active(self):
        """
        Trigger automatic renewal process of the SSO claims.

        :returns: A boolean indicating if renewal is active.
        """
        return self._core.is_session_renewal_active()

    def start_automatic_claims_renewal(self):
        """
        Trigger automatic renewal process of the SSO claims.
        """
        self._core.start_sso_renewal()

    def stop_automatic_claims_renewal(self):
        """
        Stop automatic claims renewal.
        """
        if self._core.is_session_renewal_active():
            self._core.stop_session_renewal()

    @property
    def session_id(self):
        """
        Property: session_id.

        :returns: The user's session id, or None
        """
        return self._core._session.session_id

    @property
    def cookies(self):
        """
        Property: cookies.

        :returns: The encoded cookies, or None
        """
        return self._core._session.cookies

    @property
    def session_error(self):
        """
        Property: session error.

        :returns: The session error string or ""
        """
        return self._core._session.error
