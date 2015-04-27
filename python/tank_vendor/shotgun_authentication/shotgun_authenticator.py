# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from . import interactive_authentication
from . import user
from . import user_impl
from . import session_cache
from .errors import InvalidCredentials
from .defaults_manager import DefaultsManager


class ShotgunAuthenticator(object):
    """
    Shotgun Authentication
    ----------------------

    This class is used to help maintain an authenticated Shotgun User session
    across multiple application launches and environments. By default, the
    library is not tied to any particular Shotgun site - you can use it to
    produce an authenticated user for any site of their choosing.

    The library is essentially a series of factory methods, all returning
    ShotgunUser derived instances. This instance represents an established user
    in Shotgun. You can serialize this object and pass it around, etc. The
    create_sg_connection() method returns a shotgun instance based on the
    credentials of this user. It wraps around a Shotgun connection and traps
    authentication errors so that whenever the Shotgun connection has expired,
    it is automatically renewed by prompting the user to type in their password.
    Whenever QT is available, a dialog is shown to aid in this prompting.

    If you want to customize any of the logic of how the authentication
    stores values, handles defaults or manages the behaviour in general,
    implement an DefaultsManager class and pass it to the constructor of the
    ShotgunAuthenticator object.
    """

    def __init__(self, defaults_manager=None):
        """
        Constructor

        :param defaults_manager: A DefaultsManager object that defines the basic
                                 behaviour of this authenticator. If omitted,
                                 the default, built-in DefaultsManager will be
                                 used.
        """
        self._defaults_manager = defaults_manager or DefaultsManager()

    def clear_default_user(self):
        """
        Removes the default user's credentials from disk for the default host. The
        next time the ShotgunAuthenticator.get_saved_user method is called,
        None will be returned.

        :returns: If a user was cleared, the user object is returned, None otherwise.
        """
        try:
            user = self.create_session_user(
                host=self._defaults_manager.get_host(),
                login=self._defaults_manager.get_login(),
                http_proxy=self._defaults_manager.get_http_proxy()
            )
            user.uncache_session_token()
            return user
        except InvalidCredentials:
            # Not all credentials were found, so there is no default user.
            return None

    def get_user_from_prompt(self):
        """
        Display a UI prompt (QT based UI if possible but may fall back on console)

        The DefaultsManager can be used to pre-fill the host and login name.

        :raises AuthenticationCancelled: If the user cancels the authentication process,
                                         an AuthenticationCancelled is thrown.

        :returns: The SessionUser based on the login information provided.
        """
        host, login, session_token = interactive_authentication.authenticate(
            self._defaults_manager.get_host(),
            self._defaults_manager.get_login(),
            self._defaults_manager.get_http_proxy(),
            self._defaults_manager.is_host_fixed()
        )
        return self.create_session_user(
            login=login, session_token=session_token,
            host=host, http_proxy=self._defaults_manager.get_http_proxy()
        )

    def create_session_user(self, login, session_token=None, password=None, host=None, http_proxy=None):
        """
        Create an AuthenticatedUser given a set of human user credentials.
        Either a password or session token must be supplied. If a password is supplied,
        a session token will be generated for security reasons.

        :param login: Shotgun user login
        :param session_token: Shotgun session token
        :param password: Shotgun password
        :param host: Shotgun host to log in to. If None, the default host will be used.
        :param http_proxy: Shotgun proxy to use. If None, the default http proxy will be used.

        :returns: A SessionUser instance.
        """
        # Get the defaults is arguments were None.
        host = host or self._defaults_manager.get_host()
        http_proxy = http_proxy or self._defaults_manager.get_http_proxy()

        # Create a session user
        return user.ShotgunUser(
            user_impl.SessionUser(host, login, session_token, http_proxy, password=password)
        )

    def create_script_user(self, api_script, api_key, host=None, http_proxy=None):
        """
        Create an AuthenticatedUser given a set of script credentials.

        :param script_user: Shotgun script user
        :param script_key: Shotgun script key
        :param host: Shotgun host to log in to. If None, the default host will
                     be used.
        :param http_proxy: Shotgun proxy to use. If None, the default http proxy
                           will be used.

        :returns: A ShotgunUser derived instance.
        """
        return user.ShotgunUser(
            user_impl.ScriptUser(
                host or self._defaults_manager.get_host(),
                api_script,
                api_key,
                http_proxy or self._defaults_manager.get_http_proxy(),
            )
        )

    def get_default_host(self):
        """
        Returns the host from the defaults manager.
        :returns: The default host string.
        """
        return self._defaults_manager.get_host()

    def get_default_http_proxy(self):
        """
        Returns the HTTP proxy from the defaults manager.
        :returns: The default http proxy string.
        """
        return self._defaults_manager.get_http_proxy()

    def get_default_user(self):
        """
        Returns the default user from the defaults manager.
        :returns: A ShotgunUser derived instance if available, None otherwise.
        """
        # Get the credentials
        credentials = self._defaults_manager.get_user_credentials()

        # There is no default user.
        if not credentials:
            return None

        # If this looks like an api user, delegate to create_script_user.
        # If some of the arguments are missing, don't worry, create_script_user
        # will take care of it.
        if "api_script" in credentials or "api_key" in credentials:
            return self.create_script_user(
                api_script=credentials.get("api_script"),
                api_key=credentials.get("api_key"),
                host=credentials.get("host"),
                http_proxy=credentials.get("http_proxy")
            )
        # If this looks like a session user, delegate to create_session_user.
        # If some of the arguments are missing, don't worry, create_session_user
        # will take care of it.
        elif "login" in credentials or "password" in credentials or "session_token" in credentials:
            return self.create_session_user(
                login=credentials.get("login"),
                password=credentials.get("password"),
                session_token=credentials.get("session_token"),
                host=credentials.get("host"),
                http_proxy=credentials.get("http_proxy")
            )
        # We don't know what this is, abort!
        else:
            raise InvalidCredentials(
                "unknown credentials configuration: %s" % credentials
            )

    def get_user(self):
        """
        This method will always return a valid user. It will first ask for the
        default user to the defaults manager. If none is found, the user will
        be prompted on the command line or from a dialog for their credentials.

        :returns: A ShotgunUser derived instance matching the credentials
        provided.

        :raises AuthenticationCancelled: This is raised if the user cancelled
                                         the authentication.
        """
        # Make sure we don't already have a user logged in through single
        # sign-on or provided by a DefaultsManager-derived instance.
        user = self.get_default_user()
        if user:
            return user

        # Prompt the client for user credentials and connection information
        user = self.get_user_from_prompt()

        # Remember that this user and host are the last settings used for
        # authentication in order to provide single sign-on.
        self._defaults_manager.set_host(user.host)
        self._defaults_manager.set_login(user.login)

        return user
