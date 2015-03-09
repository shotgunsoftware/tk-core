# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

from tank import errors
from tank.util import shotgun
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


class AuthenticationManager(object):
    """
    Manages authentication information.
    """

    @classmethod
    def get_instance(cls):
        """
        Returns the AuthenticationManager for this process. If no AuthenticationManager
        has been activated, Toolkit's default AuthenticationManager will be activated.
        :returns: A singleton instance of the AuthenticationManager class.
        """
        if not hasattr(AuthenticationManager, "_instance"):
            AuthenticationManager.activate()
        return AuthenticationManager._instance

    @classmethod
    def activate(cls, *args, **kwargs):
        """
        Activates an authentication manager. Any unnamed and named arguments to this method
        will be passed to the classes's initiliazation method.
        :raises: TankError if a manager has already been activated.
        """
        if hasattr(AuthenticationManager, "_instance"):
            raise errors.TankError(
                "An AuthenticationManager has already been activated: %s" %
                AuthenticationManager._instance.__class__.__name__
            )
        setattr(AuthenticationManager, "_instance", cls(*args, **kwargs))

    @staticmethod
    def deactivate():
        """
        Deactivates the current authentication manager.
        :raises: TankError if a manager has not been activated.
        """
        if not hasattr(AuthenticationManager, "_instance"):
            raise errors.TankError("No AuthenticationManager have been activated yet.")
        delattr(AuthenticationManager, "_instance")

    def __init__(self):
        """
        Constructor.
        """
        self._core_config_data = shotgun.get_associated_sg_config_data()

    def get_host(self):
        """
        Returns the current host.
        :returns: A string with the hostname.
        """
        return self._core_config_data.get("host")

    def get_http_proxy(self):
        """
        Returns the optional http_proxy.
        :returns: A string with the hostname of the proxy. Can be None.
        """
        return self._core_config_data.get("http_proxy")

    def get_credentials(self):
        """
        Retrieves the credentials for the current user.
        :returns: A dictionary holding the credentials that were found. Can either contains keys:
                  - api_script and api_key
                  - login, session_token
                  - an empty dictionary.
                  The dictionary will be empty if no credentials were found.
        """
        # Break circular dependency by importing locally.
        script_user_credentials = self._get_script_user_credentials()
        if script_user_credentials:
            return script_user_credentials

        host = self.get_host()
        if not host:
            return {}
        login_info = self._get_login_info(host)
        if login_info:
            return login_info
        else:
            return {}

    def get_connection_information(self):
        """
        Returns a dictionary with connection parameters and user credentials.
        :returns: A dictionary with keys host, http_proxy and all the keys returned from get_credentials.
        """
        connection_info = {}
        connection_info["host"] = self.get_host()
        connection_info["http_proxy"] = self.get_http_proxy()
        connection_info.update(self.get_credentials())
        return connection_info

    def clear_cached_credentials(self):
        """
        Clears any cached credentials.
        """
        self._delete_session_data()

    def cache_connection_information(self, host, login, session_token):
        """
        Caches authentication credentials.
        :param host: Host to cache.
        :param login: Login to cache.
        :param session_token: Session token to cache.
        """
        # For now, only cache session data to disk.
        self._cache_session_data(host, login, session_token)

    def _slice_dict(self, dictionary, *keys):
        """
        Extracts all fields passed in from a dictionary.
        :param dictionary: Dictionary we want to get a slice of.
        :param keys: List of keys that need to be extracted.
        :returns: A dictionary containing at most all the keys that were specified.
        """
        return {k: v for k, v in dictionary.iteritems() if k in keys}

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
        from tank.util import path
        return os.path.join(
            path.get_local_site_cache_location(base_url),
            "authentication",
            "login.ini"
        )

    def _get_script_user_credentials(self):
        """
        Returns the script user credentials
        """
        from .authentication import _is_script_user_authenticated
        if _is_script_user_authenticated(self._core_config_data):
            return {
                "api_key": self._core_config_data.get("api_key"),
                "api_script": self._core_config_data.get("api_script")
            }
        else:
            return {}

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
