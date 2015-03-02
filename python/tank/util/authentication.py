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
from tank.errors import TankAuthenticationError
from ConfigParser import SafeConfigParser
from tank.util import shotgun

# FIXME: Quick hack to easily disable logging in this module while keeping the
# code compatible. We have to disable it by default because Maya will print all out
# debug strings.
if False:
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


def _get_login_info_location(base_url):
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


def _is_session_token_cached():
    """
    Returns if there is a cached session token for the current user.
    :returns: True is there is, False otherwise.
    """
    if get_login_info(shotgun.get_associated_sg_config_data()["host"]):
        return True
    else:

        return False


def get_login_info(base_url):
    """
    Returns the cached login info if found.
    :param base_url: The site we want the login information for.
    :returns: Returns a dictionary with keys login and session_token or None
    """
    # Retrieve the location of the cached info
    info_path = _get_login_info_location(base_url)
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


def cache_session_data(host, login, session_token):
    """
    Caches the session data for a site and a user.
    :param host: Site we want to cache a session for.
    :param login: User we want to cache a session for.
    :param session_token: Session token we want to cache.
    """
    # Retrieve the cached info file location from the host
    info_path = _get_login_info_location(host)

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


def _delete_session_data():
    """
    Clears the session cache for a given site.
    """
    host = shotgun.get_associated_sg_base_url()
    logger.debug("Clearing session cached on disk.")
    try:
        info_path = _get_login_info_location(host)
        if os.path.exists(info_path):
            logger.debug("Session file found.")
            os.remove(info_path)
            logger.debug("Session cleared.")
        else:
            logger.debug("Session file not found: %s", info_path)
    except:
        logger.exception("Couldn't delete the site cache file")


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


def _is_script_user_authenticated(config_data):
    """
    Indicates if we are authenticating with a script user for a given configuration.
    :param config_data: The configuration data.
    :returns: True is we are using a script user, False otherwise.
    """
    return "api_script" in config_data and "api_key" in config_data


def _is_human_user_authenticated(config_data):
    """
    Indicates if we are authenticating with a user.
    :param config_data: The configuration data.
    :returns: True is we are using a session, False otherwise.
    """
    # Try to create a connection. If something is create, we are authenticated.
    return _create_sg_connection_from_session(config_data) is not None


def is_human_user_authenticated():
    """
    Indicates if we authenticated with a user.
    :returns: True is we are using a user, False otherwise.
    """
    return _is_human_user_authenticated(shotgun.get_associated_sg_config_data())


def is_authenticated():
    """
    Indicates if we need to authenticate.
    :returns: True is we are using a script user or have a valid session token, False otherwise.
    """
    config_data = shotgun.get_associated_sg_config_data()
    return _is_script_user_authenticated(config_data) or _is_human_user_authenticated(config_data)


# FIXME: When Manne's work on app store credential refactoring is merged, we can go ahead and
# remove the config data parameter and retrieve it directly inside this method.
def _create_or_renew_sg_connection_from_session(config_data):
    """
    Creates a shotgun connection using the current session token or a new one if the old one
    expired.
    :param config_data: A dictionary holding the "host" and "http_proxy"
    :returns: A valid Shotgun instance.
    :raises TankAuthenticationError: If we couldn't get a valid session, a TankError is thrown.
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


def _create_sg_connection_from_session(config_data=None):
    """
    Tries to auto login to the site using the existing session_token that was saved.
    :returns: Returns a Shotgun instance.
    """
    logger.debug("Trying to auto-login")
    # Retrieve the config data from shotgun.yml and the associated login info if we didn't
    # received it from the caller.
    if not config_data:
        logger.debug("No configuration data provided, retrieving default configuration.")
        config_data = shotgun.get_associated_sg_config_data()

    login_info = get_login_info(config_data["host"])
    if not login_info:
        return None

    # Try to refresh the data
    logger.debug("Validating token.")

    sg = _validate_session_token(
        config_data["host"],
        login_info["session_token"],
        config_data.get("http_proxy")
    )
    if sg:
        logger.debug("Token is still valid!")
        return sg
    else:
        # Session token was invalid, so uncache it to make sure nobody else tries using it.
        _delete_session_data()
        logger.debug("Failed refreshing the token.")
        return None


def create_sg_connection_from_script_user(config_data=None):
    """
    Create a Shotgun connection based on a script user.
    :param config_data: A dictionary with keys host, api_script, api_key and an optional http_proxy
    :returns: A Shotgun instance.
    """
    return _shotgun_instance_factory(
        config_data["host"],
        config_data["api_script"],
        config_data["api_key"],
        http_proxy=config_data.get("http_proxy", None)
    )


def create_authenticated_sg_connection():
    """
    Creates an authenticated Shotgun connection.
    :param config_data: A dictionary holding the site configuration.
    :returns: A Shotgun instance.
    """
    config_data = shotgun.get_associated_sg_config_data()
    # If no configuration information
    if _is_script_user_authenticated(config_data):
        # create API
        return create_sg_connection_from_script_user(config_data)
    else:
        return _create_or_renew_sg_connection_from_session(config_data)


def logout():
    """
    Logs out of the currently cached session.
    :returns: True is logging out was successful, False is no session was cached.
    """
    if _is_session_token_cached():
        _delete_session_data()
        return True
    else:
        return False
