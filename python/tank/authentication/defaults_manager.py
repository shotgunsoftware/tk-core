# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from . import session_cache

class DefaultsManager(object):
    """
    The defaults manager allows a client of the Shotgun Authenticator class
    to customize various behaviors around data storage and settings.

    By default, when you construct a :class:`ShotgunAuthenticator` object, it will be
    instantiated with a standard defaults manager implementation. This will
    work for most cases - user session credentials will be stored in a file
    on disk and the system maintains a concept of a current user and a current
    host.

    The defaults manager will also look in multiple locations for a file called ``config.ini``
    in order to provide appropriate defaults:

        - The SGTK_CONFIG_LOCATION environment variable,
        - The SGTK_DESKTOP_CONFIG_LOCATION environment variable.
        - The ~/Library/Application Support/Shotgun/config.ini file
        - The ~/Library/Caches/Shotgun/desktop/config/config.ini file
        - One of the fallback locations specified in the :meth:``~DefaultsManager.__init__``

    .. code-block:: ini
        # Login related settings
        #
        [Login]

        # If specified, the username text input on the login screen will be populated
        # with this value when logging into the Shotgun Desktop for the very first time.
        # Defaults to the user's OS login.
        #
        default_login=$USERNAME

        # If specified, the site text input on the login screen will be populated with
        # this value when logging into the Shotgun Desktop for the very first time.
        # Defaults to https://mystudio.shotgunstudio.com.
        #
        default_site=https://your-site-here.shotgunstudio.com

        # If specified, the Shotgun Desktop will use these proxy settings to connect to
        # the Shotgun site and the Toolkit App Store. The proxy string should be of the
        # forms 123.123.123.123, 123.123.123.123:8888 or
        # username:pass@123.123.123.123:8888.
        # Empty by default.
        #
        http_proxy=123.234.345.456:8888

        # If specified, the Shotgun API Desktop will use these proxy settings to connect
        # to the Toolkit App Store. The proxy string format is the same as http_proxy.
        # If the setting is present in the file but not set, then no proxy will be used
        # to connect to the Toolkit App Store, regardless of the value of the http_proxy
        # setting.
        # Empty by default.
        #
        app_store_http_proxy=123.234.345.456:8888

    If, however, you want to implement a custom behavior around how defaults
    are managed, simply derive from this class and pass your custom instance
    to the :class:`ShotgunAuthenticator` object when you construct it.
    """

    def __init__(self):
        """
        Constructor.
        """
        # Breaks circular dependency between util and authentication framework
        from ..util.user_settings import UserSettings
        self._user_settings = UserSettings()

    def is_host_fixed(self):
        """
        When doing an interactive login, this indicates if the user can decide
        the host to connect to. In its default implementation, the :class:`DefaultsManager`
        will indicate that the host is not fixed, meaning that the user will be
        presented with an option to pick a site at login time.

        With something like Toolkit, where each project already have a specific
        site association, you typically want to override this to return True,
        indicating to the authenticator not to ask the user which site they want
        to log in to.

        :returns: False if the user should be given an option to decide which host
                  to log in to, True if the host is already predetermined and cannot
                  be changed by the user.
        """
        return False

    def get_host(self):
        """
        The default host is used as a useful starting point when doing
        interactive authentication. When the host is not fixed (see the
        :meth:`is_host_fixed` method), the return value of get_host is what is
        used to implement single sign-on between all Toolkit desktop
        applications (at the moment, tank and Shotgun Desktop).

        The default implementation maintains a concept of a "current host"
        which will be presented as a default to users when they are
        logging in.

        When the host is fixed, this must return a value and this value will
        be used as an absolute rather than a default suggested to the user.

        :returns: A string containing the default host name.
        """
        return session_cache.get_current_host() or self._user_settings.default_site

    def set_host(self, host):
        """
        Called by the authentication system when a new host has been defined.

        :param host: The new default host.
        """
        # Host is fixed, don't update the default host.
        if self.is_host_fixed():
            return
        session_cache.set_current_host(host)

    def get_http_proxy(self):
        """
        Called by the authentication system when it needs to retrieve the
        proxy settings to use for a Shotgun connection.

        The format should be the same as is being used in the Shotgun API.
        For more information, see the Shotgun API documentation:
        https://github.com/shotgunsoftware/python-api/wiki/Reference%3A-Methods#shotgun

        :returns: String containing the default http proxy, None by default.
        """
        return self._user_settings.default_http_proxy

    def get_login(self):
        """
        Called by the authentication system when it needs to get a
        value for the login. Typically this is used to populate UI
        fields with defaults.

        :returns: Default implementation returns the login for the
                  currently stored user.
        """
        return session_cache.get_current_user(self.get_host()) or self._user_settings.default_login

    def get_user_credentials(self):
        """
        Called by the authentication system when it requests a default or current user.

        A dictionary with a login and a session token should be returned, which will
        allow the authentication system to authenticate the user.

        The default implementation maintains a concept where it stores the currently
        authenticated user and its session token and tries to return this if possible,
        effectively meaning that the user will be automatically logged in without having
        to be prompted.

        This is typically subclassed if you want to track the notion of a current
        user in an alternative way or maintain a separate notion of the "current" user,
        separate from the default user maintained by the default implementation.

        Toolkit uses the default implementation and will therefore remember the user's
        credentials across all DCCs and tools.

        :returns: A dictionary either with keys login and session_token in the case
                  of a normal Shotgun User, keys api_script and api_key in the case of a Script
                  User or None in case no credentials could be established.
        """
        if self.get_host() and self.get_login():
            return session_cache.get_session_data(self.get_host(), self.get_login())
        else:
            return None

    def set_login(self, login):
        """
        Called by the authentication system when a new user is being logged in.

        The default implementation maintains a concept of a default user
        (returned via the get_user_credentials) and whenever the login is set
        via this method, the default user will change to be this login instead.

        :param login: login as string
        """
        self._login = login
        session_cache.set_current_user(self.get_host(), login)
