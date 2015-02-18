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
Session management for Toolkit.
"""

import os
import logging

from tank_vendor.shotgun_api3 import Shotgun
from tank_vendor.shotgun_api3 import AuthenticationFault
from tank.errors import TankAuthenticationError
from ConfigParser import SafeConfigParser
from tank.util import shotgun
from tank.util import path

# Configure logging
logger = logging.getLogger("sgtk.session")
# logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

_shotgun_instance_factory = Shotgun


def _get_cached_login_info_location(base_url):
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


def is_session_token_cached():
    """
    Returns if there is a cached session token for the current user.
    :returns: True is there is, False otherwise.
    """
    if get_cached_login_info(shotgun.get_associated_sg_config_data()["host"]):
        return True
    else:

        return False


def get_cached_login_info(base_url):
    """
    Returns the cached login info if found.
    :returns: Returns a dictionnary with keys login and session_token or None
    """
    # Retrieve the location of the cached info
    info_path = _get_cached_login_info_location(base_url)
    # Nothing was cached, return an empty dictionary.
    if not os.path.exists(info_path):
        logger.debug("No cache found at %s", info_path)
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
            logger.debug("Incomplete settings (login:%s, session_token:%s)", login, session_token)
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
    info_path = _get_cached_login_info_location(host)

    # make sure the info_dir exists!
    info_dir, info_file = os.path.split(info_path)
    path.ensure_path_exists(info_dir)

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


def delete_session_data(host):
    """
    Clears the session cache for a given site.
    :param host: Site to clear the session for.
    """
    logger.debug("Clearing session cached on disk.")
    try:
        info_path = _get_cached_login_info_location(host)
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
    except:
        # We couldn't login, so try again.
        logging.exception("There was a problem logging in.")


def create_sg_connection_from_session(config_data=None):
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

    login_info = get_cached_login_info(config_data["host"])
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
        delete_session_data(config_data["host"])
        logger.debug("Failed refreshing the token.")
        return None
