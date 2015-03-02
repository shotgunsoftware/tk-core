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
UI and console based login for Toolkit.
"""

# Using "with" with the lock to make sure it is always released.
from __future__ import with_statement
from getpass import getpass
import logging
import threading

from tank.errors import TankAuthenticationError, TankAuthenticationDisabled
from tank.util import authentication
from tank.util.login import get_login_name
from tank.util import shotgun

# FIXME: Quick hack to easily disable logging in this module while keeping the
# code compatible. We have to disable it by default because Maya will print all out
# debug strings.
if False:
    # Configure logging
    logger = logging.getLogger("sgtk.interactive_authentication")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())
else:
    class logger:
        @staticmethod
        def debug(*args, **kwargs):
            pass

        @staticmethod
        def info(*args, **kwargs):
            pass

        @staticmethod
        def warning(*args, **kwargs):
            pass

        @staticmethod
        def error(*args, **kwargs):
            pass

        @staticmethod
        def exception(*args, **kwargs):
            pass


class AuthenticationHandlerBase(object):
    """
    Base class for authentication requests. It handles locking reading cached credentials
    on disk and writing newer credentials back. It also keeps track of any attempt to cancel
    authentication.
    """

    _authentication_lock = threading.Lock()
    """
    Lock the assures only one thread at a time can execute the authentication logic.
    """
    _authentication_disabled = False
    """
    Flag that keeps track if a user cancelled authentication. When the flag is raised, it will
    be impossible to authenticate again.
    """

    def authenticate(self, force_human_user_authentication):
        """
        Common login logic, regardless of how we are actually logging in. It will first try to reuse
        any existing session and if that fails then it will ask for credentials and upon success
        the credentials will be cached.
        :param force_human_user_authentication: Indicates if we should force authentication to be user based.
                                                Setting to True disables automatic authentication as a script_user.
        """
        with AuthenticationHandlerBase._authentication_lock:
            # If we are authenticated, we're done here.
            if force_human_user_authentication and authentication.is_human_user_authenticated():
                return
            elif not force_human_user_authentication and authentication.is_authenticated():
                return
            # If somebody disabled authentication, we're done here as well.
            elif AuthenticationHandlerBase._authentication_disabled:
                raise TankAuthenticationDisabled()

            config_data = shotgun.get_associated_sg_config_data()

            # We might not have login information, in that case use an empty dictionary.
            login_info = authentication.get_login_info(config_data["host"]) or {}

            try:
                logger.debug("Not authenticated, requesting user input.")
                # Do the actually credentials prompting and authenticating.
                hostname, login, session_token = self._do_authentication(
                    config_data["host"],
                    login_info.get("login", get_login_name()),
                    config_data.get("http_proxy")
                )
            except TankAuthenticationError:
                AuthenticationHandlerBase._authentication_disabled = True
                logger.debug("Authentication cancelled, disabling authentication.")
                raise

            logger.debug("Login successful!")

            # Cache the credentials so subsequent session based logins can reuse the session id.
            authentication.cache_session_data(hostname, login, session_token)

    def _do_authentication(self, host, login, http_proxy):
        """
        Does the actual authentication. Prompts the user and validates the credentials.
        :param host Host to authenticate for.
        :param login: User that needs authentication.
        :param http_proxy: Proxy to connect to when authenticating.
        :raises: TankAuthenticationError If the user cancels the authentication process,
                 this exception will be thrown.
        """
        raise NotImplementedError

    def _get_session_token(self, hostname, login, password, http_proxy):
        """
        Retrieves a session token for the given credentials.
        :param hostname: The host to connect to.
        :param login: The user to get a session for.
        :param password: Password for the user.
        :param http_proxy: Proxy to use. Can be None.
        :returns: If the credentials were valid, returns a session token, otherwise returns None.
        """
        try:
            return authentication.generate_session_token(hostname, login, password, http_proxy)
        except TankAuthenticationError:
            print "Authentication failed."
            return None

    def raise_no_credentials_provided_error(self):
        raise TankAuthenticationError("No credentials provided.")


class ConsoleAuthenticationHandlerBase(AuthenticationHandlerBase):
    """
    Base class for authenticating on the console. It will take care of the credential retrieval loop,
    requesting new credentials as long as they are invalid or until the user provides the right one
    or cancels the authentication.
    """

    def _do_authentication(self, hostname, login, http_proxy):
        """
        Prompts the user for this password to retrieve a new session token and rewews
        the session token.
        :param hostname: Host to renew a token for.
        :param login: User to renew a token for.
        :param http_proxy: Proxy to use for the request. Can be None.
        :returns: The (session token, login user) tuple.
        """
        logger.debug("Requesting password on command line.")
        while True:
            # Get the credentials from the user
            try:
                login, password = self._get_user_credentials(hostname, login)
            except EOFError:
                # Insert a \n on the current line so the print is displayed on a new time.
                print
                self.raise_no_credentials_provided_error()

            session_token = self._get_session_token(hostname, login, password, http_proxy)
            if session_token:
                return hostname, login, session_token

    def _get_user_credentials(self, hostname, login):
        """
        Prompts the user for his credentials.
        :param host Host to authenticate for.
        :param login: User that needs authentication.
        :param http_proxy: Proxy to connect to when authenticating.
        :raises: TankAuthenticationError If the user cancels the authentication process,
                 this exception will be thrown.
        """
        raise NotImplementedError

    def _get_password(self):
        """
        Prompts the user for his password. The password will not be visible on the console.
        :raises: TankAuthenticationError If the user enters an empty password, the exception
                                         will be thrown.
        """
        password = getpass("Password (empty to abort): ")
        if not password:
            self.raise_no_credentials_provided_error()
        return password

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
            user_input = raw_input(text) or default_value
        return user_input


class ConsoleRenewSessionHandler(ConsoleAuthenticationHandlerBase):
    """
    Handles session renewal. Prompts for the user's password.
    """
    def _get_user_credentials(self, hostname, login):
        """
        Reads the user password from the keyboard.
        :param hostname: Name of the host we will be logging on.
        :param login: Current user
        :returns: The user's password.
        """
        print "%s, your current session has expired." % login
        print "Please enter your password to renew your session for %s" % hostname
        return login, self._get_password()


class ConsoleLoginHandler(ConsoleAuthenticationHandlerBase):
    """
    Handles username/password authentication.
    """
    def _get_user_credentials(self, hostname, login):
        """
        Reads the user credentials from the keyboard.
        :param hostname: Name of the host we will be logging on.
        :param login: Default value for the login.
        :returns: A tuple of (login, password) strings.
        """
        print "Please enter your login credentials for %s" % hostname
        login = self._get_keyboard_input("Login", login)
        password = self._get_password()
        return login, password


class UiAuthenticationHandler(AuthenticationHandlerBase):
    """
    Handles ui based authentication.
    """

    def __init__(self, is_session_renewal):
        """
        Creates the UiAuthenticationHandler object.
        :param is_session_renewal: Boolean indicating if we are renewing a session. True if we are, False otherwise.
        """
        self._is_session_renewal = is_session_renewal

    def _do_authentication(self, hostname, login, http_proxy):
        """
        Pops a dialog that asks for the hostname, login and password of the user. If there is a current
        engine, it will run the code in the main thread.
        :param hostname: Host to display in the dialog.
        :param login: login to display in the dialog.
        :param http_proxy: Proxy server to use when validating credentials. Can be None.
        :returns: A tuple of (hostname, login, session_token)
        """
        from .qt import login_dialog

        from tank.platform import engine

        if self._is_session_renewal:
            logger.debug("Requesting password in a dialog.")
        else:
            logger.debug("Requesting username and password in a dialog.")

        def _process_ui():
            dlg = login_dialog.LoginDialog(
                "Shotgun Login",
                is_session_renewal=self._is_session_renewal,
                hostname=hostname,
                login=login,
                http_proxy=http_proxy
            )
            return dlg.result()

        # If there is a current engine, execute from the main thread.
        if engine.current_engine():
            result = engine.current_engine().execute_in_main_thread(_process_ui)
        else:
            # Otherwise just run in the current one.
            result = _process_ui()
        if not result:
            self.raise_no_credentials_provided_error()
        return result


def ui_renew_session():
    """
    Prompts the user to enter his password in a dialog to retrieve a new session token.
    """
    # Force human user authentication, since ression renewal is always in the context of a user login.
    UiAuthenticationHandler(is_session_renewal=True).authenticate(force_human_user_authentication=True)


def ui_authenticate(force_human_user_authentication=False):
    """
    Authenticates the current process. Authentication can be done through script user authentication
    or human user authentication. If doing human user authentication and there is no session cached, a
    dialgo asking for user credentials will appear.
    :param force_human_user_authentication: If force_human_user_authentication is set to True, any configured
                                            script user will be ignored.
    """
    UiAuthenticationHandler(is_session_renewal=False).authenticate(force_human_user_authentication)


def console_renew_session():
    """
    Prompts the user to enter his password on the command line to retrieve a new session token.
    """
    # Force human user authentication, since ression renewal is always in the context of a user login.
    ConsoleRenewSessionHandler().authenticate(force_human_user_authentication=True)


def console_authenticate(force_human_user_authentication=False):
    """
    Authenticates the current process. Authentication can be done through script user authentication
    or human user authentication. If doing human user authentication and there is no session cached, the
    user credentials will be retrieved from the console.
    :param force_human_user_authentication: If force_human_user_authentication is set to True, any configured
                                            script user will be ignored.
    """
    ConsoleLoginHandler().authenticate(force_human_user_authentication)


def console_logout():
    """
    Logs out of the currently cached session and prints whether it worked or not.
    """
    if authentication.logout():
        print "Succesfully logged out of", shotgun.get_associated_sg_base_url()
    else:
        print "Not logged in."
