# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Shotgun authentication for Toolkit
"""

import os
import logging

from tank_vendor.shotgun_api3 import Shotgun
from tank_vendor.shotgun_api3.lib import httplib2
from tank_vendor.shotgun_api3 import AuthenticationFault, ProtocolError
from tank.errors import TankError, TankAuthenticationError
from ConfigParser import SafeConfigParser
from tank.util import shotgun

# FIXME: Quick hack to easily disable logging in this module while keeping the
# code compatible. We have to disable it by default because Maya will print all out
# debug strings.
if True:
    # Configure logging
    logger = logging.getLogger("sgtk.authentication")
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


# Having the factory as an indirection to create a shotgun instance allows us to tweak unit tests
# more easily
_shotgun_instance_factory = Shotgun


def _is_session_token_cached():
    """
    Returns if there is a cached session token for the current user.
    :returns: True is there is, False otherwise.
    """
    if _is_human_user_authenticated(get_authentication_credentials()):
        return True
    else:
        return False


def _validate_session_token(host, session_token, http_proxy):
    """
    Validates the session token by attempting to an authenticated request on the site.
    :param session_token: Session token to use to connect to the host.
    :param host: Host for that session
    :param http_proxy: http_proxy to use to connect. If no proxy is required, provide None or an empty string.
    :returns: A Shotgun instance if the session token was valid, None otherwise.
    """
    # Connect to the site
    logger.debug("Creating shotgun instance")
    sg = _shotgun_instance_factory(
        host,
        session_token=session_token,
        http_proxy=http_proxy
    )
    try:
        sg.find_one("HumanUser", [])
        return sg
    except AuthenticationFault, e:
        # Session was expired.
        logger.exception(e)
        return None


def generate_session_token(hostname, login, password, http_proxy):
    """
    Generates a session token for a given username/password on a given site.
    :param hostname: The host to connect to.
    :param login: The user to get a session for.
    :param password: Password for the user.
    :param http_proxy: Proxy to use. Can be None.
    :returns: The generated session token for that user/password/site combo.
    :raises: TankAuthenticationError if the credentials were invalid.
    """
    try:
        # Create the instance...
        sg = _shotgun_instance_factory(
            hostname,
            login=login,
            password=password,
            http_proxy=http_proxy
        )
        # .. and generate the session token. If it throws, we have invalid credentials.
        return sg.get_session_token()
    except AuthenticationFault:
        raise TankAuthenticationError("Authentication failed.")
    except (ProtocolError, httplib2.ServerNotFoundError):
        raise TankAuthenticationError("Server %s was not found." % hostname)
    except:
        # We couldn't login, so try again.
        logging.exception("There was a problem logging in.")


def _is_script_user_authenticated(authentication_data):
    """
    Indicates if we are authenticating with a script user for a given configuration.
    :param authentication_data: Information used to authenticate.
    :returns: True is "api script" and "api_key" are present, False otherwise.
    """
    return "api_script" in authentication_data and "api_key" in authentication_data


def _is_human_user_authenticated(authentication_data):
    """
    Indicates if we are authenticating with a user.
    :param authentication_data: Information used to authenticate.
    :returns: True is we are using a session, False otherwise.
    """
    # Try to create a connection. If something is created, we are authenticated.
    return _create_sg_connection_from_session(authentication_data) is not None


def is_human_user_authenticated():
    """
    Indicates if we authenticated with a user.
    :returns: True is we are using a user, False otherwise.
    """
    return _is_human_user_authenticated(get_authentication_credentials())


def is_authenticated():
    """
    Indicates if we need to authenticate.
    :returns: True is we are using a script user or have a valid session token, False otherwise.
    """
    authentication_data = get_authentication_credentials()
    return _is_script_user_authenticated(authentication_data) or _is_human_user_authenticated(authentication_data)


def _create_or_renew_sg_connection_from_session(config_data):
    """
    Creates a shotgun connection using the current session token or a new one if the old one
    expired.
    :param config_data: A dictionary holding the "host" and "http_proxy"
    :returns: A valid Shotgun instance.
    :raises TankAuthenticationError: If we couldn't get a valid session, a TankAuthenticationError is thrown.
    """
    from ..platform import engine

    # If the Shotgun login was not automated, then try to create a Shotgun
    # instance from the cached session id.
    sg = _create_sg_connection_from_session(config_data)
    # If that didn't work
    if not sg:
        # If there is a current engine, we can ask the engine to prompt the user to login
        if engine.current_engine():
            engine.current_engine().renew_session()
            sg = _create_sg_connection_from_session(config_data)
            if not sg:
                raise TankAuthenticationError("Authentication failed.")
        else:
            # Otherwise we failed and can't login.
            raise TankAuthenticationError("No authentication credentials were found.")
    return sg


def _create_sg_connection_from_session(authentication_credentials):
    """
    Tries to auto login to the site using the existing session_token that was saved.
    :param authentication_credentials: Authentication credentials.
    :returns: Returns a Shotgun instance.
    """
    logger.debug("Trying to auto-login")

    if "login" not in authentication_credentials or "session_token" not in authentication_credentials:
        logger.debug("Nothing was cached.")
        return None

    # Try to refresh the data
    logger.debug("Validating token.")

    sg = _validate_session_token(
        authentication_credentials["host"],
        authentication_credentials["session_token"],
        authentication_credentials.get("http_proxy")
    )
    if sg:
        logger.debug("Token is still valid!")
        return sg
    else:
        # Session token was invalid, so uncache it to make sure nobody else tries using it.
        AuthenticationManager.get_instance().clear_cached_credentials()
        logger.debug("Failed refreshing the token.")
        return None


def create_sg_connection_from_script_user(authentication_credentials):
    """
    Create a Shotgun connection based on a script user.
    :param authentication_credentials: A dictionary with keys host, api_script, api_key and an optional http_proxy.
    :returns: A Shotgun instance.
    """
    return _shotgun_instance_factory(
        authentication_credentials["host"],
        authentication_credentials["api_script"],
        authentication_credentials["api_key"],
        http_proxy=authentication_credentials.get("http_proxy", None)
    )


def create_authenticated_sg_connection():
    """
    Creates an authenticated Shotgun connection.
    :param config_data: A dictionary holding the site configuration.
    :returns: A Shotgun instance.
    """
    authentication_credentials = get_authentication_credentials()
    # If no configuration information
    if _is_script_user_authenticated(authentication_credentials):
        # create API
        return create_sg_connection_from_script_user(authentication_credentials)
    else:
        return _create_or_renew_sg_connection_from_session(authentication_credentials)


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
            raise TankError("AuthenticationManager can't be activated twice.")
        setattr(AuthenticationManager, "_instance", cls(*args, **kwargs))

    @staticmethod
    def deactivate():
        if not hasattr(AuthenticationManager, "_instance"):
            raise TankError("No AuthenticationManager have been activated yet.")
        delattr(AuthenticationManager, "_instance")

    def __init__(self):
        """
        Constructor.
        """
        self._core_config_data = shotgun.get_associated_sg_config_data()
        self._force_human_user_authentication = False

    def get_host(self):
        """
        Returns the current host.
        :returns: A string with the hostname.
        """
        return self._core_config_data["host"]

    def get_http_proxy(self):
        """
        Returns the optional http_proxy.
        :returns: A string with the hostname of the proxy. Can be None.
        """
        return self._core_config_data.get("http_proxy")

    def get_credentials(self, force_human_user_authentication):
        """
        Retrieves the credentials for the current user.
        :param force_human_user_authentication: Skips script user credentials if True.
        :returns: A dictionary holding the credentials that were found. Can either contains keys:
                  - api_script and api_key
                  - login, session_token
                  - an empty dictionary.
                  The dictionary will be empty if no credentials were found.
        """
        force = self._force_human_user_authentication or force_human_user_authentication
        if not force and _is_script_user_authenticated(self._core_config_data):
            return self._slice_dict(self._core_config_data, "api_script", "api_key")
        else:
            login_info = self._get_login_info(self.get_host())
            if login_info:
                return self._slice_dict(login_info, "login", "session_token")
            else:
                return {}

    def get_authentication_credentials(self, force_human_user_authentication):
        """
        Returns a dictionary with connection parameters and user credentials.
        :param force_human_user_authentication: Skips script user credentials if True.
        :returns: A dictionary with keys host, http_proxy and all the keys returned from get_credentials.
        """
        connection_info = {}
        connection_info["host"] = self.get_host()
        connection_info["http_proxy"] = self.get_http_proxy()
        connection_info.update(self.get_credentials(force_human_user_authentication))
        return connection_info

    def clear_cached_credentials(self):
        """
        Clears any cached credentials.
        """
        self._delete_session_data()

    def cache_authentication_credentials(self, host, login, session_token):
        """
        Caches authentication credentials.
        :param host: Host to cache.
        :param login: Login to cache.
        :param session_token: Session token to cache.
        """
        self._force_human_user_authentication = True
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


def get_authentication_credentials(force_human_user_authentication=False):
    """
    Retrieves the authentication credentials.
    :returns: A dictionary with credentials to connect to a site. If the authentication is made using
              a script user, a dictionary with the following keys will be returned: host, api_script, api_key.
              If the authentication is made using a human user, a dictionary with the following keys will
              be returned: host, login, session_token. In both cases, an optional http_proxy entry can be present.
    """
    return AuthenticationManager.get_instance().get_authentication_credentials(force_human_user_authentication)


def clear_cached_credentials():
    """
    Clears cached credentials.
    """
    AuthenticationManager.get_instance().clear_cached_credentials()


def cache_authentication_credentials(host, login, session_token):
    """
    Caches authentication credentials.
    :param host: Host to cache.
    :param login: Login to cache.
    :param session_token: Session token to cache.
    """
    AuthenticationManager.get_instance().cache_authentication_credentials(host, login, session_token)


def logout():
    """
    Logs out of the currently cached session.
    :returns: True is logging out was successful, False is no session was cached.
    """
    if _is_session_token_cached():
        # Forget the current hostname.
        AuthenticationManager.get_instance().clear_cached_credentials()
        return True
    else:
        return False
