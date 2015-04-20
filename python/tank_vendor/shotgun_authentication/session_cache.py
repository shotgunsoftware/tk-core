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
This module will provide basic i/o to read and write session user's credentials
in the site's cache location.
"""

from __future__ import with_statement
import os
import sys
import urlparse
from tank_vendor.shotgun_api3 import Shotgun, AuthenticationFault, ProtocolError
from tank_vendor.shotgun_api3.lib import httplib2
from tank_vendor import yaml
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


def _get_cache_location():
    """
    Returns an OS specific cache location.

    :returns: Path to the OS specific cache folder.
    """
    if sys.platform == "darwin":
        root = os.path.expanduser("~/Library/Caches/Shotgun")
    elif sys.platform == "win32":
        root = os.path.join(os.environ["APPDATA"], "Shotgun")
    elif sys.platform.startswith("linux"):
        root = os.path.expanduser("~/.shotgun")
    return root


def _get_local_site_cache_location(base_url):
    """
    Returns the location of the site cache root based on a site.

    :param base_url: Site we need to compute the root path for.

    :returns: An absolute path to the site cache root.
    """
    return os.path.join(
        _get_cache_location(),
        # get site only; https://www.foo.com:8080 -> www.foo.com
        urlparse.urlparse(base_url)[1].split(":")[0]
    )


def _get_authentication_cache_location(base_url):
    """
    Returns the location for the authentication cache folder for a given site.

    :param base_url: Site we need to compute the authentication cache path for.

    :returns: An absolute path to the authentication cache root.
    """
    return os.path.join(
        _get_local_site_cache_location(base_url),
        "authentication"
    )


def _get_users_file_location(base_url):
    """
    Returns the location of the users file on disk for a specific site.

    :param base_url: The site we want the login information for.

    :returns: Path to the login information.
    """
    return os.path.join(
        _get_authentication_cache_location(base_url),
        "users.yml"
    )


def _get_current_user_file_location(base_url):
    """
    Returns the location of the users file on disk for a specific site.

    :param base_url: The site we want the login information for.

    :returns: Path to the login information.
    """
    return os.path.join(
        _get_authentication_cache_location(base_url),
        "current_user.yml"
    )


def _ensure_folder_for_file(filepath):
    """
    Makes sure the folder exists for a given file.

    :param filepath: Path to the file we want to make sure the parent directory
                     exists.

    :returns: The path to the file.
    """
    folder, _ = os.path.split(filepath)
    if not os.path.exists(folder):
        os.makedirs(folder, 0700)
    return filepath


def _try_load_yaml_file(file_path):
    """
    Loads a yaml file.

    :param file_path: The yaml file to load.

    :returns: The dictionary for this yaml file. If the file doesn't exist or is
              corrupted, returns an empty dictionary.
    """

    if not os.path.exists(file_path):
        logger.debug("Yaml file missing: %s" % file_path)
        return {}
    try:
        # Open the file and read it.
        with open(file_path, "r") as config_file:
            return yaml.load(config_file)
    except yaml.YAMLError:
        # Return to the beginning
        config_file.seek(0)
        logger.error("File '%s' is corrupted!" % file_path)
        # And log the complete file for debugging.
        for line in config_file:
            # Log line without \n
            logger.debug(line.rstrip())
        # Create an empty document
        return {}


def _try_load_users_file(file_path):
    """
    Loads or creates on the file the data for the users file. The users file has the following format:
        users:
           {name: "login", session_token: "session_token"}
           {name: "login", session_token: "session_token"}
           {name: "login", session_token: "session_token"}
    """
    content = _try_load_yaml_file(file_path)
    # Make sure any mandatory entry is present.
    content.setdefault("users", [])
    return content


def _try_load_current_user_file(file_path):
    """
    Loads or creates the users file
    """
    content = _try_load_yaml_file(file_path)
    # Make sure any mandatody entry is present.
    content.setdefault("current_user", None)
    return content


def _insert_or_update_user(users_file, login, session_token):
    """
    Finds or updates an entry in the users file with the given login and
    session token.

    :param users_file: Users dictionary to update.
    :param login: Login of the user to update.
    :param session_token: Session token of the user to update.
    """
    for user in users_file["users"]:
        if user["login"] == login:
            user["session_token"] = session_token
            return
    users_file["users"].append({"login": login, "session_token": session_token})


def _write_users_file(file_path, users_data):
    """
    Writes the users file at a given location.

    :param file_path: Where to write the users data
    :param users_data: Dictionary to write to disk.
    """
    with open(file_path, "w") as users_file:
        yaml.dump(users_data, users_file)


def delete_session_data(host, login):
    """
    Clears the session cache for the given site and login.

    :param host: Site to clear the session cache for.
    :param login: User to clear the session cache for.
    """
    if not host:
        logger.error("Current host not set, nothing to clear.")
        return
    logger.debug("Clearing session cached on disk.")
    try:
        info_path = _get_users_file_location(host)
        logger.debug("Session file found.")
        # Read in the file
        users_file = _try_load_users_file(info_path)
        # File the users to remove the token
        users_file["users"] = [u for u in users_file["users"] if u.get("login") != login]
        # Write back the file.
        _write_users_file(info_path, users_file)
        logger.debug("Session cleared.")
    except:
        logger.exception("Couldn't update the session cache file!")
        raise


def get_session_data(base_url, login):
    """
    Returns the cached login info if found.

    :param base_url: The site to look for the login information.
    :param login: The user we want the login information for.

    :returns: Returns a dictionary with keys login and session_token or None
    """
    # Retrieve the location of the cached info
    info_path = _get_users_file_location(base_url)
    try:
        # Nothing was cached, return an empty dictionary.
        users_file = _try_load_users_file(info_path)
        for user in users_file["users"]:
            if user.get("login") == login:
                return {
                    "login": user["login"],
                    "session_token": user["session_token"]
                }
        logger.debug("No cache found at %s" % info_path)
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
    file_path = _get_users_file_location(host)
    _ensure_folder_for_file(file_path)

    logger.debug("Caching login info at %s...", file_path)

    document = _try_load_users_file(file_path)
    _insert_or_update_user(document, login, session_token)
    _write_users_file(file_path, document)

    logger.debug("Cached!")


def get_current_user(host):
    """
    Returns the current user for the given host.

    :param host: Host to fetch the current for.

    :returns: The current user for this host or None if not set.
    """
    # Retrieve the cached info file location from the host
    info_path = _get_current_user_file_location(host)
    if os.path.exists(info_path):
        document = _try_load_current_user_file(info_path)
        return document["current_user"]
    return None


def set_current_user(host, login):
    """
    Saves the current user for a given host.

    :param host: Host to save the current user for.
    :param login: The current user login for specified host.
    """
    file_path = _get_current_user_file_location(host)
    _ensure_folder_for_file(file_path)

    current_user_file = _try_load_current_user_file(file_path)
    current_user_file["current_user"] = login
    _write_users_file(file_path, current_user_file)


def generate_session_token(hostname, login, password, http_proxy):
    """
    Generates a session token for a given username/password on a given site.

    :param hostname: The host to connect to.
    :param login: The user to get a session for.
    :param password: Password for the user.
    :param http_proxy: Proxy to use. Can be None.

    :returns: The generated session token for that user/password/site combo.

    :raises: AuthenticationError if the credentials were invalid.
    """
    try:
        # Create the instance taht does not connect right away for speed...
        sg = Shotgun(
            hostname,
            login=login,
            password=password,
            http_proxy=http_proxy,
            connect=False
        )
        # .. and generate the session token. If it throws, we have invalid
        # credentials or invalid host/proxy settings.
        return sg.get_session_token()
    except AuthenticationFault:
        raise AuthenticationError("Authentication failed.")
    except (ProtocolError, httplib2.ServerNotFoundError):
        raise AuthenticationError("Server %s was not found." % hostname)
    except:
        logger.exception("There was a problem logging in.")
        raise
