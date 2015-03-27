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
from tank_vendor.shotgun_api3 import Shotgun, AuthenticationFault, ProtocolError
from tank_vendor.shotgun_api3.lib import httplib2
from .errors import AuthenticationError

# FIXME: Quick hack to easily disable logging in this module while keeping the
# code compatible. We have to disable it by default because Maya will print all out
# debug strings.
if False:
    import logging
    # Configure logging
    logger = logging.getLogger("sgtk.session_cache")
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


def get_session_data_location(base_url):
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


def delete_session_data(host):
    """
    Clears the session cache for the current site.
    """
    if not host:
        logger.error("Current host not set, nothing to clear.")
        return
    logger.debug("Clearing session cached on disk.")
    try:
        info_path = get_session_data_location(host)
        if os.path.exists(info_path):
            logger.debug("Session file found.")
            os.remove(info_path)
            logger.debug("Session cleared.")
        else:
            logger.debug("Session file not found: %s", info_path)
    except:
        logger.exception("Couldn't delete the site cache file")


def get_session_data(base_url):
    """
    Returns the cached login info if found.
    :param base_url: The site we want the login information for.
    :returns: Returns a dictionary with keys login and session_token or None
    """
    # Retrieve the location of the cached info
    info_path = get_session_data_location(base_url)
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


def cache_session_data(host, login, session_token):
    """
    Caches the session data for a site and a user.
    :param host: Site we want to cache a session for.
    :param login: User we want to cache a session for.
    :param session_token: Session token we want to cache.
    """
    # Retrieve the cached info file location from the host
    info_path = get_session_data_location(host)

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


def generate_session_token(hostname, login, password, http_proxy):
    """
    Generates a session token for a given username/password on a given site.
    :param hostname: The host to connect to.
    :param login: The user to get a session for.
    :param password: Password for the user.
    :param http_proxy: Proxy to use. Can be None.
    :param shotgun_instance_factory: Shotgun API instance factory. Defaults to Shotgun.
    :returns: The generated session token for that user/password/site combo.
    :raises: TankAuthenticationError if the credentials were invalid.
    """
    try:
        # Create the instance...
        sg = Shotgun(
            hostname,
            login=login,
            password=password,
            http_proxy=http_proxy
        )
        # .. and generate the session token. If it throws, we have invalid credentials.
        return sg.get_session_token()
    except AuthenticationFault:
        raise AuthenticationError("Authentication failed.")
    except (ProtocolError, httplib2.ServerNotFoundError):
        raise AuthenticationError("Server %s was not found." % hostname)
    except:
        logger.exception("There was a problem logging in.")
        raise
