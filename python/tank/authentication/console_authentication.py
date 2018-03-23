# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Console based authentication. This module implements UX and prompting for a
workflow where the user gets prompted via stdin/stdout.

--------------------------------------------------------------------------------
NOTE! This module is part of the authentication library internals and should
not be called directly. Interfaces and implementation of this module may change
at any point.
--------------------------------------------------------------------------------
"""
from __future__ import print_function

from . import session_cache
from .. import LogManager
from .errors import AuthenticationError, AuthenticationCancelled, ConsoleLoginWithSSONotSupportedError
from tank_vendor import shotgun_api3
from tank_vendor.shotgun_api3 import MissingTwoFactorAuthenticationFault
from .sso_saml2 import is_sso_enabled_on_site
from ..util.shotgun.connection import sanitize_url

from getpass import getpass

logger = LogManager.get_logger(__name__)


class ConsoleAuthenticationHandlerBase(object):
    """
    Base class for authenticating on the console. It will take care of the credential retrieval loop,
    requesting new credentials as long as they are invalid or until the user provides the right one
    or cancels the authentication. This class should not be instantiated directly, instead it is used
    through the authenticate and renew_session methods.
    """

    def authenticate(self, hostname, login, http_proxy):
        """
        Prompts the user for this password to retrieve a new session token and rewews
        the session token.
        :param hostname: Host to renew a token for.
        :param login: User to renew a token for.
        :param http_proxy: Proxy to use for the request. Can be None.
        :returns: The (hostname, login, session_token, session_metadata) tuple.
        :raises AuthenticationCancelled: If the user aborts the login process, this exception
                                         is raised.

        """
        logger.debug("Requesting password on command line.")
        while True:
            # Get the credentials from the user
            try:
                hostname, login, password = self._get_user_credentials(hostname, login, http_proxy)
            except EOFError:
                # Insert a \n on the current line so the print is displayed on a new time.
                print()
                raise AuthenticationCancelled()

            try:
                try:
                    # Try to generate a session token and return the user info.
                    return hostname, login, session_cache.generate_session_token(
                        hostname, login, password, http_proxy
                    ), None
                except MissingTwoFactorAuthenticationFault:
                    # session_token was None, we need 2fa.
                    code = self._get_2fa_code()
                    # Ask again for a token using 2fa this time. If this throws an AuthenticationError because
                    # the code is invalid or already used, it will be caught by the except clause beneath.
                    return hostname, login, session_cache.generate_session_token(
                        hostname, login, password, http_proxy, auth_token=code
                    ), None
            except AuthenticationError:
                # If any combination of credentials are invalid (user + invalid pass or
                # user + valid pass + invalid 2da code) we'll end up here.
                print("Login failed.")
                print()

    def _get_user_credentials(self, hostname, login, http_proxy):
        """
        Prompts the user for his credentials.
        :param host Host to authenticate for.
        :param login: User that needs authentication.
        :param http_proxy: Proxy to connect to when authenticating.
        :returns: The (hostname, login, plain text password) tuple.
        :raises AuthenticationCancelled: If the user cancels the authentication process,
                this exception will be thrown.
        """
        raise NotImplementedError

    def _get_password(self):
        """
        Prompts the user for his password. The password will not be visible on the console.
        :returns: Plain text password.
        :raises AuthenticationCancelled: If the user enters an empty password, the exception
                                         will be thrown.
        """
        password = getpass("Password (empty to abort): ")
        if not password:
            raise AuthenticationCancelled()
        return password

    def _read_clean_input(self, text):
        """
        Reads a line a text from the keyboard and strips any trailing or tailing
        whitespaces.

        :param text: Text to display before prompting the user.

        :returns: The user's text input.
        """
        return raw_input(text).strip()

    def _get_keyboard_input(self, label, default_value=""):
        """
        Queries for keyboard input.
        :param label: The name of the input we require.
        :param default_value: The value to use if the user has entered no input.
        :returns: The user input or default_value if nothing was entered.
        """
        text = label
        if default_value:
            text += " [%s]" % default_value
        text += ": "
        user_input = None
        while not user_input:
            user_input = self._read_clean_input(text) or default_value
        # Strip whitespace before and after user input.
        return user_input

    def _get_2fa_code(self):
        """
        Prompts the user for his 2fa code.
        :returns: Two factor authentication code.
        :raises AuthenticationCancelled: If the user enters an empty code, the exception will be
                                         thrown.
        """
        code = self._read_clean_input("Two factor authentication code (empty to abort): ")
        if not code:
            raise AuthenticationCancelled()
        return code


class ConsoleRenewSessionHandler(ConsoleAuthenticationHandlerBase):
    """
    Handles session renewal. Prompts for the user's password. This class should
    not be instantiated directly and be used through the authenticate and
    renew_session methods.
    """

    def _get_user_credentials(self, hostname, login, http_proxy):
        """
        Reads the user password from the keyboard.
        :param hostname: Name of the host we will be logging on.
        :param login: Current user
        :param http_proxy: Proxy to connect to when authenticating.
        :returns: The (hostname, login, plain text password) tuple.
        """
        print("%s, your current session has expired." % login)

        if is_sso_enabled_on_site(shotgun_api3, hostname, http_proxy):
            raise ConsoleLoginWithSSONotSupportedError(hostname)

        print("Please enter your password to renew your session for %s" % hostname)
        return hostname, login, self._get_password()


class ConsoleLoginHandler(ConsoleAuthenticationHandlerBase):
    """
    Handles username/password authentication. This class should not be
    instantiated directly and be used through the authenticate and renew_session
    methods.
    """

    def __init__(self, fixed_host):
        """
        Constructor.
        """
        super(ConsoleLoginHandler, self).__init__()
        self._fixed_host = fixed_host

    def _get_user_credentials(self, hostname, login, http_proxy):
        """
        Reads the user credentials from the keyboard.
        :param hostname: Name of the host we will be logging on.
        :param login: Default value for the login.
        :param http_proxy: Proxy to connect to when authenticating.
        :returns: A tuple of (login, password) strings.
        """
        if self._fixed_host:
            if is_sso_enabled_on_site(shotgun_api3, hostname, http_proxy):
                raise ConsoleLoginWithSSONotSupportedError(hostname)
            print("Please enter your login credentials for %s" % hostname)

        else:
            print("Please enter your login credentials.")
            hostname = self._get_keyboard_input("Host", hostname)
            if is_sso_enabled_on_site(shotgun_api3, hostname, http_proxy):
                raise ConsoleLoginWithSSONotSupportedError(hostname)

        login = self._get_keyboard_input("Login", login)
        password = self._get_password()
        return sanitize_url(hostname), login, password
