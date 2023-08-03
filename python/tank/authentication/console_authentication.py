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

from . import constants
from . import session_cache
from .. import LogManager
from .errors import (
    AuthenticationError,
    AuthenticationCancelled,
    ConsoleLoginNotSupportedError,
)
from tank_vendor.shotgun_api3 import MissingTwoFactorAuthenticationFault
from .sso_saml2 import (
    is_sso_enabled_on_site,
    is_unified_login_flow2_enabled_on_site,
    is_autodesk_identity_enabled_on_site,
)
from .unified_login_flow2 import authentication as ulf2_authentication
from ..util.shotgun.connection import sanitize_url

from getpass import getpass
import webbrowser
from tank_vendor.six.moves import input

logger = LogManager.get_logger(__name__)


def _assert_console_session_is_supported(hostname, http_proxy):
    """
    Simple utility method which will raise an exception if using a
    username/password pair is not supported by the Shotgun server.
    Which is the case when using SSO or Autodesk Identity.
    """
    if is_unified_login_flow2_enabled_on_site(hostname, http_proxy):
        # OK we support that in console
        pass
    elif is_sso_enabled_on_site(hostname, http_proxy):
        raise ConsoleLoginNotSupportedError(hostname, "Single Sign-On")
    elif is_autodesk_identity_enabled_on_site(hostname, http_proxy):
        raise ConsoleLoginNotSupportedError(hostname, "Autodesk Identity")


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
        print("[ShotGrid Authentication]\n")
        while True:
            # Get the SG URL from the user or from the given hostname
            try:
                hostname = self._get_sg_url(hostname, http_proxy)
            except EOFError:
                # Insert a \n on the current line so the print is displayed on a new line.
                print()
                raise AuthenticationCancelled()

            hostname = sanitize_url(hostname)
            _assert_console_session_is_supported(hostname, http_proxy)

            auth_fn = self._get_auth_method(hostname, http_proxy)
            try:
                return auth_fn(hostname, login, http_proxy)
            except AuthenticationError as error:
                # If any combination of credentials are invalid (user + invalid pass or
                # user + valid pass + invalid 2da code) we'll end up here.
                print("Login failed: %s" % error)
                print()

    def _authenticate_legacy(self, hostname, login, http_proxy):
        # Get the credentials from the user
        try:
            hostname, login, password = self._get_user_credentials(
                hostname, login, http_proxy
            )
        except EOFError:
            # Insert a \n on the current line so the print is displayed on a new line.
            print()
            raise AuthenticationCancelled()

        try:
            # Try to generate a session token and return the user info.
            return (
                hostname,
                login,
                session_cache.generate_session_token(
                    hostname, login, password, http_proxy
                ),
                None,
            )
        except MissingTwoFactorAuthenticationFault:
            # session_token was None, we need 2fa.
            code = self._get_2fa_code()
            # Ask again for a token using 2fa this time. If this throws an AuthenticationError because
            # the code is invalid or already used, it will be caught by the except clause beneath.
            return (
                hostname,
                login,
                session_cache.generate_session_token(
                    hostname, login, password, http_proxy, auth_token=code
                ),
                None,
            )

    def _authenticate_unified_login_flow2(self, hostname, login, http_proxy):
        print()
        print(
            "Authenticating to {sg_url} requires your web browser.\n"
            "\n"
            'After selecting "continue", your default web browser will open '
            "and prompt you to authenticate to {sg_url} if you are not already "
            "authenticated to this site in the browser.\n"
            "\n"
            "Then, you will be prompted to approve the authentication request "
            "and return to this application.\n"
            "\n"
            'Select "Approve" and come back to this application.'
            "\n".format(sg_url=hostname)
        )

        self._read_clean_input("Press enter when you are ready to continue.")
        print("\n")  # Always have 2 empty lines after a prompt
        print(
            "Stand by... your default browser will open shortly for you to "
            "approve the authentication request.\n"
            "\n"
            "After approving the authentication request, return to this "
            "application."
        )
        print()
        session_info = ulf2_authentication.process(
            hostname,
            http_proxy=http_proxy,
            product="toolkit",  # Same as "PRODUCT_IDENTIFIER" from LoginDialog
            browser_open_callback=webbrowser.open,
        )

        print()
        if not session_info:
            raise AuthenticationError("The web authentication failed.")

        print(
            "Success! The web authentication has been approved and your "
            "application is ready to use."
        )
        return session_info

    def _get_auth_method(self, hostname, http_proxy):
        if not is_unified_login_flow2_enabled_on_site(hostname, http_proxy):
            return self._authenticate_legacy

        if is_autodesk_identity_enabled_on_site(
            hostname, http_proxy
        ) or is_sso_enabled_on_site(hostname, http_proxy):
            return self._authenticate_unified_login_flow2

        # We have 2 choices here
        methods = {
            "1": {
                "value": constants.METHOD_ULF2,
                "function": self._authenticate_unified_login_flow2,
            },
            "2": {
                "value": constants.METHOD_BASIC,
                "function": self._authenticate_legacy,
            },
        }

        # Let's see which method the user chose previously for this site
        method_saved = session_cache.get_preferred_method(hostname)
        method_default = "1"
        for k, v in methods.items():
            if v["value"] == method_saved:
                method_default = k
                break

        # Then prompt them to chose
        print(
            "\n"
            "The ShotGrid site support two authentication methods:\n"
            " 1. App Session Launcher using your local web browser\n"
            " 2. Legacy method using login/password\n"
        )

        method_selected = self._get_keyboard_input(
            "Select a method (1 or 2)",
            default_value=method_default,
        )

        method = methods.get(method_selected)
        if not method:
            raise AuthenticationError(
                "Unsupported authentication method choice {m}".format(m=method)
            )

        session_cache.set_preferred_method(hostname, method["value"])
        return method["function"]

    def _get_sg_url(self, hostname, http_proxy):
        """
        Prompts the user for the SG host.
        :param host Host to authenticate for.
        :param http_proxy: Proxy to connect to when authenticating.
        :returns: The hostname.
        :raises AuthenticationCancelled: If the user cancels the authentication process,
                this exception will be thrown.
        """
        raise NotImplementedError

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
        return input(text).strip()

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

        print()
        # Strip whitespace before and after user input.
        return user_input

    def _get_2fa_code(self):
        """
        Prompts the user for his 2fa code.
        :returns: Two factor authentication code.
        :raises AuthenticationCancelled: If the user enters an empty code, the exception will be
                                         thrown.
        """
        code = self._read_clean_input(
            "Two factor authentication code (empty to abort): "
        )
        if not code:
            raise AuthenticationCancelled()
        return code


class ConsoleRenewSessionHandler(ConsoleAuthenticationHandlerBase):
    """
    Handles session renewal. Prompts for the user's password. This class should
    not be instantiated directly and be used through the authenticate and
    renew_session methods.
    """

    def _get_sg_url(self, hostname, http_proxy):
        return hostname

    def _get_user_credentials(self, hostname, login, http_proxy):
        """
        Reads the user password from the keyboard.
        :param hostname: Name of the host we will be logging on.
        :param login: Current user
        :param http_proxy: Proxy to connect to when authenticating.
        :returns: The (hostname, login, plain text password) tuple.
        """
        print("%s, your current session has expired." % login)

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

    def _get_sg_url(self, hostname, http_proxy):
        if self._fixed_host:
            return hostname

        recent_hosts = session_cache.get_recent_hosts()
        # If we have a recent host and it's not in the list, add it.
        # This can happen if a user logs on and while the process is running the
        # host is removed from the host list.
        if hostname and hostname not in recent_hosts:
            recent_hosts.insert(0, hostname)

        if len(recent_hosts) > 1:
            print("Recent ShotGrid sites:")
            for sg_url in recent_hosts:
                print("  *", sg_url)
            print()

        return self._get_keyboard_input(
            "Enter the ShotGrid site URL for authentication",
            hostname,
        )

    def _get_user_credentials(self, hostname, login, http_proxy):
        """
        Reads the user credentials from the keyboard.
        :param hostname: Name of the host we will be logging on.
        :param login: Default value for the login.
        :param http_proxy: Proxy to connect to when authenticating.
        :returns: A tuple of (login, password) strings.
        """
        if self._fixed_host:
            print("Please enter your login credentials for %s" % hostname)

        login = self._get_keyboard_input("Login", login)
        password = self._get_password()
        return hostname, login, password
