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
This module provides the basic implementation of the AuthenticationManager. It will read and write
credentials in the site's cache location.
"""

import os
import sys
import urlparse
from ConfigParser import SafeConfigParser

# FIXME: Quick hack to easily disable logging in this module while keeping the
# code compatible. We have to disable it by default because Maya will print all out
# debug strings.
if False:
    import logging
    # Configure logging
    logger = logging.getLogger("sgtk.authentication_manager")
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


def _get_local_site_cache_location(base_url):
    """
    Returns the location of the site cache root based on a site.
    :param base_url: Site we need to compute the root path for.
    :returns: An absolute path to the site cache root.
    """
    if sys.platform == "darwin":
        root = os.path.expanduser("~/Library/Caches/Shotgun")
    elif sys.platform == "win32":
        root = os.path.join(os.environ["APPDATA"], "Shotgun")
    elif sys.platform.startswith("linux"):
        root = os.path.expanduser("~/.shotgun")

    # get site only; https://www.foo.com:8080 -> www.foo.com
    base_url = urlparse.urlparse(base_url)[1].split(":")[0]

    return os.path.join(root, base_url)


class ActivationError(Exception):
    pass


class AuthenticationManager(object):
    """
    Manages authentication information.
    """

    __instance = None

    @staticmethod
    def get_instance():
        """
        Returns the AuthenticationManager for this process. If no AuthenticationManager
        has been activated, Toolkit's default AuthenticationManager will be activated.
        :returns: A singleton instance of the AuthenticationManager class.
        """
        if not AuthenticationManager.is_activated():
            raise ActivationError("No AuthenticationManager have been activated yet.")
        return AuthenticationManager.__instance

    @classmethod
    def activate(cls, *args, **kwargs):
        """
        Activates an authentication manager. Any unnamed and named arguments to this method
        will be passed to the classes's initiliazation method.
        :raises: TankError if a manager has already been activated.
        """
        logger.debug("Activating authentication manager: %s @ %s" % (cls.__name__, cls.__module__))
        if AuthenticationManager.is_activated():
            raise ActivationError(
                "An AuthenticationManager has already been activated: %s" %
                AuthenticationManager.get_instance().__class__.__name__
            )
        AuthenticationManager.__instance = cls(*args, **kwargs)

    @staticmethod
    def deactivate():
        """
        Deactivates the current authentication manager.
        :raises: TankError if a manager has not been activated.
        """
        if not AuthenticationManager.is_activated():
            raise ActivationError("No AuthenticationManager have been activated yet.")
        logger.debug(
            "Deactivating authentication manager: %s @ %s" %
            (AuthenticationManager.__instance.__class__.__name__,
             AuthenticationManager.__instance.__class__.__module__)
        )
        AuthenticationManager.__instance = None

    @staticmethod
    def is_activated():
        """
        Indicates if there is already an instance set.
        """
        return AuthenticationManager.__instance is not None

    @staticmethod
    def is_human_user_authenticated(connection_information):
        """
        Indicates if we are authenticating with a user.
        :param connection_information: Information used to connect to Shotgun.
        :returns: True is we are using a session, False otherwise.
        """
        from . import connection
        # Try to create a connection. If something is created, we are authenticated.
        is_human_user = connection.create_sg_connection_from_session(connection_information) is not None
        logger.debug("is_human_user: %s" % is_human_user)
        return is_human_user

    @staticmethod
    def is_script_user_authenticated(connection_information):
        """
        Indicates if we are authenticating with a script user for a given configuration.
        :param connection_information: Information used to connect to Shotgun.
        :returns: True is "api script" and "api_key" are present, False otherwise.
        """
        return connection_information.get("api_script") and connection_information.get("api_key")

    def __init__(self):
        """
        Constructor.
        """
        self._current_host = None

    def get_host(self):
        """
        Returns the current host.
        :returns: A string with the hostname.
        """
        return self._current_host

    def get_http_proxy(self):
        """
        Returns the optional http_proxy.
        :returns: A string with the hostname of the proxy. Can be None.
        """
        return None

    def get_credentials(self):
        """
        Retrieves the credentials for the current user.
        :returns: A dictionary holding the credentials that were found. Can either contains keys:
                  - login, session_token
                  - an empty dictionary.
                  The dictionary will be empty if no credentials were found.
        """
        host = self.get_host()
        logger.debug("Getting human user credentials for host %s" % host)
        if not host:
            logger.debug("No host found!")
            return {}
        login_info = self._get_login_info(host)
        if login_info:
            logger.debug("Login info found: %s" % login_info)
            return login_info
        else:
            logger.debug("Login info not found")
            return {}

    def get_connection_information(self):
        """
        Returns a dictionary with connection parameters and user credentials.
        :returns: A dictionary with keys host, http_proxy and all the keys returned from get_credentials.
        """
        logger.debug("Getting connection information")
        connection_info = {}
        connection_info["host"] = self.get_host()
        connection_info["http_proxy"] = self.get_http_proxy()
        connection_info.update(self.get_credentials())
        return connection_info

    def logout(self):
        """
        Logs out of the currently cached session.
        :returns: The connection information before it was cleared if logged in, None otherwise.
        """
        connection_information = self.get_connection_information()
        if AuthenticationManager.is_human_user_authenticated(connection_information):
            self.clear_cached_credentials()
            return connection_information
        else:
            return None

    def is_authenticated(self):
        """
        Indicates if we need to authenticate.
        :returns: True is we are authenticated, False otherwise.
        """
        return self._is_authenticated(self.get_connection_information())

    def _is_authenticated(self, connection_information):
        """
        Actual implementation of the is_authenticated test. This is the method to override in derived classes.
        :param connection_information: Information used to connect to Shotgun.
        :returns: True is we are authenticated, False otherwise.
        """
        return AuthenticationManager.is_human_user_authenticated(connection_information)

    def clear_cached_credentials(self):
        """
        Clears any cached credentials.
        """
        self._current_host = None
        self._delete_session_data()

    def cache_connection_information(self, host, login, session_token):
        """
        Caches authentication credentials.
        :param host: Host to cache.
        :param login: Login to cache.
        :param session_token: Session token to cache.
        """
        self._current_host = host
        # For now, only cache session data to disk.
        self._cache_session_data(host, login, session_token)

    def _delete_session_data(self):
        """
        Clears the session cache for the current site.
        """
        host = self.get_host()
        if not host:
            logger.error("Current host not set, nothing to clear.")
            return
        logger.debug("Clearing session cached on disk.")
        try:
            info_path = self._get_login_info_location(host)
            if os.path.exists(info_path):
                logger.debug("Session file found.")
                os.remove(info_path)
                logger.debug("Session cleared.")
            else:
                logger.debug("Session file not found: %s", info_path)
        except:
            logger.exception("Couldn't delete the site cache file")

    def _get_login_info(self, base_url):
        """
        Returns the cached login info if found.
        :param base_url: The site we want the login information for.
        :returns: Returns a dictionary with keys login and session_token or None
        """
        # Retrieve the location of the cached info
        info_path = self._get_login_info_location(base_url)
        # Nothing was cached, return an empty dictionary.
        if not os.path.exists(info_path):
            logger.debug("No cache found at %s" % info_path)
            return None
        try:
            # Read the login information
            config = SafeConfigParser({"login": None, "session_token": None})
            config.read(info_path)
            if not config.has_section("LoginInfo"):
                logger.debug("No Login info was found")
                return None

            login = config.get("LoginInfo", "login", raw=True)
            session_token = config.get("LoginInfo", "session_token", raw=True)

            if not login or not session_token:
                logger.debug("Incomplete settings (login:%s, session_token:%s)" % (login, session_token))
                return None

            return {"login": login, "session_token": session_token}
        except Exception:
            logger.exception("Exception thrown while loading cached session info.")
            return None

    def _get_login_info_location(self, base_url):
        """
        Returns the location of the session file on disk for a specific site.
        :param base_url: The site we want the login information for.
        :returns: Path to the login information.
        """
        return os.path.join(
            _get_local_site_cache_location(base_url),
            "authentication",
            "login.ini"
        )

    def _cache_session_data(self, host, login, session_token):
        """
        Caches the session data for a site and a user.
        :param host: Site we want to cache a session for.
        :param login: User we want to cache a session for.
        :param session_token: Session token we want to cache.
        """
        # Retrieve the cached info file location from the host
        info_path = self._get_login_info_location(host)

        # make sure the info_dir exists!
        info_dir, info_file = os.path.split(info_path)
        if not os.path.exists(info_dir):
            os.makedirs(info_dir, 0700)

        logger.debug("Caching login info at %s...", info_path)
        # Create a document with the following format:
        # [LoginInfo]
        # login=username
        # session_token=some_unique_id
        config = SafeConfigParser()
        config.add_section("LoginInfo")
        config.set("LoginInfo", "login", login)
        config.set("LoginInfo", "session_token", session_token)
        # Write it to disk.
        with open(info_path, "w") as configfile:
            config.write(configfile)
        logger.debug("Cached!")
