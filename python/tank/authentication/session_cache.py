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

--------------------------------------------------------------------------------
NOTE! This module is part of the authentication library internals and should
not be called directly. Interfaces and implementation of this module may change
at any point.
--------------------------------------------------------------------------------
"""

from __future__ import with_statement
import os
import socket
from tank_vendor.shotgun_api3 import (Shotgun, AuthenticationFault, ProtocolError,
                                      MissingTwoFactorAuthenticationFault)
from tank_vendor.shotgun_api3.lib import httplib2
from tank_vendor import yaml
from .errors import AuthenticationError
from .. import LogManager

logger = LogManager.get_logger(__name__)

_CURRENT_HOST = "current_host"
_CURRENT_USER = "current_user"
_CURRENT_COOKIES = "current_cookies"
_USERS = "users"
_LOGIN = "login"
_SESSION_TOKEN = "session_token"
_SESSION_CACHE_FILE_NAME = "authentication.yml"

def _is_same_user(session_data, login):
    """
    Compares the session data's login with a given login name. The comparison
    is not case sensitive.

    :param session_data: Dictionary with keys 'login' and 'session_token'.
    :param login: Login of a user.

    :returns: True if the session data is for the given login.
    """
    return session_data.get(_LOGIN, "").lower().strip() == login.lower().strip()


def _get_global_authentication_file_location():
    """
    Returns the location of the authentication file on disk. This file
    stores authentication related information for all sites. At this moment,
    the file stores only the current host.

    Looks for the latest file naming convention first, if that doesn't exists
    tries to fall back to previous path standards.

    :returns: Path to the login information.
    """
    # avoid cylic imports
    from ..util import LocalFileStorageManager

    # try current generation path first
    path = os.path.join(
        LocalFileStorageManager.get_global_root(LocalFileStorageManager.CACHE),
        _SESSION_CACHE_FILE_NAME
    )
    if not os.path.exists(path):

        # see if there is a legacy path
        old_path = os.path.join(
            LocalFileStorageManager.get_global_root(
                LocalFileStorageManager.CACHE,
                generation=LocalFileStorageManager.CORE_V17),
            _SESSION_CACHE_FILE_NAME
        )

        if os.path.exists(old_path):
            path = old_path

    return path

def _get_site_authentication_file_location(base_url):
    """
    Returns the location of the users file on disk for a specific site.

    Looks for the latest file naming convention first, if that doesn't exists
    tries to fall back to previous path standards.

    :param base_url: The site we want the login information for.
    :returns: Path to the login information.
    """
    # avoid cylic imports
    from ..util import LocalFileStorageManager

    path = os.path.join(
        LocalFileStorageManager.get_site_root(
            base_url,
            LocalFileStorageManager.CACHE
        ),
        _SESSION_CACHE_FILE_NAME
    )

    if not os.path.exists(path):

        # see if there is a legacy path
        old_path = os.path.join(
            LocalFileStorageManager.get_site_root(
                base_url,
                LocalFileStorageManager.CACHE,
                generation=LocalFileStorageManager.CORE_V17
            ),
            _SESSION_CACHE_FILE_NAME
        )

        if os.path.exists(old_path):
            path = old_path

    return path

def _ensure_folder_for_file(filepath):
    """
    Makes sure the folder exists for a given file.

    :param filepath: Path to the file we want to make sure the parent directory
                     exists.

    :returns: The path to the file.
    """
    folder, _ = os.path.split(filepath)
    if not os.path.exists(folder):
        old_umask = os.umask(0077)
        try:
            os.makedirs(folder, 0700)
        finally:
            os.umask(old_umask)
    return filepath


def _try_load_yaml_file(file_path):
    """
    Loads a yaml file.

    :param file_path: The yaml file to load.

    :returns: The dictionary for this yaml file. If the file doesn't exist or is
              corrupted, returns an empty dictionary.
    """
    logger.debug("Loading '%s'" % file_path)
    if not os.path.exists(file_path):
        logger.debug("Yaml file missing: %s" % file_path)
        return {}
    try:
        config_file = None
        # Open the file and read it.
        config_file = open(file_path, "r")
        result = yaml.load(config_file)
        # Make sure we got a dictionary back.
        if isinstance(result, dict):
            return result
        else:
            logger.warning("File '%s' didn't have a dictionary, defaulting to an empty one.")
            return {}
    except yaml.YAMLError:
        # Return to the beginning
        config_file.seek(0)
        logger.exception("Error reading '%s'" % file_path)

        logger.debug("Here's its content:")
        # And log the complete file for debugging.
        for line in config_file:
            # Log line without \n
            logger.debug(line.rstrip())
        # Create an empty document
        return {}
    except:
        logger.exception("Unexpected error while opening %s" % file_path)
        return {}
    finally:
        # If the exception occured when we opened the file, there is no file to close.
        if config_file:
            config_file.close()


def _try_load_site_authentication_file(file_path):
    """
    Returns the site level authentication data.
    This is loaded in from disk if available,
    otherwise an empty data structure is returned.

    The users file has the following format:
        current_user: "login1"
        users:
           {name: "login1", session_token: "session_token"}
           {name: "login2", session_token: "session_token"}
           {name: "login3", session_token: "session_token"}

    :returns: site authentication style dictionary
    """
    content = _try_load_yaml_file(file_path)
    # Make sure any mandatory entry is present.
    content.setdefault(_USERS, [])
    content.setdefault(_CURRENT_USER, None)
    content.setdefault(_CURRENT_COOKIES, None)
    return content


def _try_load_global_authentication_file(file_path):
    """
    Returns the global authentication data.
    This is loaded in from disk if available,
    otherwise an empty data structure is returned.

    :returns: global authentication style dictionary
    """
    content = _try_load_yaml_file(file_path)
    # Make sure any mandatody entry is present.
    content.setdefault(_CURRENT_HOST, None)
    return content


def _insert_or_update_user(users_file, login, session_token):
    """
    Finds or updates an entry in the users file with the given login and
    session token.

    :param users_file: Users dictionary to update.
    :param login: Login of the user to update.
    :param session_token: Session token of the user to update.

    :returns: True is the users dictionary has been updated, False otherwise.
    """
    # Go through all users
    for user in users_file[_USERS]:
        # If we've matched what we are looking for.
        if _is_same_user(user, login):
            # Update and return True only if something changed.
            if user[_SESSION_TOKEN] != session_token:
                user[_SESSION_TOKEN] = session_token
                return True
            else:
                return False
    # This is a new user, add it to the list.
    users_file[_USERS].append({_LOGIN: login, _SESSION_TOKEN: session_token})
    return True


def _write_yaml_file(file_path, users_data):
    """
    Writes the yaml file at a given location.

    :param file_path: Where to write the users data
    :param users_data: Dictionary to write to disk.
    """
    print "vvvvvvvvvvvvvvvv"
    print "_write_yaml_file: %s" % users_data
    print "^^^^^^^^^^^^^^^^"
    old_umask = os.umask(0077)
    try:
        with open(file_path, "w") as users_file:
            yaml.safe_dump(users_data, users_file)
    finally:
        os.umask(old_umask)


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
        info_path = _get_site_authentication_file_location(host)
        logger.debug("Session file found.")
        # Read in the file
        users_file = _try_load_site_authentication_file(info_path)
        # File the users to remove the token
        users_file[_USERS] = [u for u in users_file[_USERS] if not _is_same_user(u, login)]
        # Write back the file.
        _write_yaml_file(info_path, users_file)
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
    info_path = _get_site_authentication_file_location(base_url)
    try:
        users_file = _try_load_site_authentication_file(info_path)
        for user in users_file[_USERS]:
            # Search for the user in the users dictionary.
            if _is_same_user(user, login):
                return {
                    # There used to be a time where we didn't strip whitepsaces
                    # before writing the file, so do it now just in case.
                    _LOGIN: user[_LOGIN].strip(),
                    _SESSION_TOKEN: user[_SESSION_TOKEN]
                }
        logger.debug("No cached user found for %s" % login)
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
    file_path = _get_site_authentication_file_location(host)
    _ensure_folder_for_file(file_path)

    logger.debug("Checking if we need to update cached session data "
                 "for site '%s' and user '%s' in %s..." % (host, login, file_path))

    document = _try_load_site_authentication_file(file_path)

    if _insert_or_update_user(document, login, session_token):
        # Write back the file only it a new user was added.
        _write_yaml_file(file_path, document)
        logger.debug("Updated session cache data.")
    else:
        logger.debug("Session data was already up to date.")


def get_current_user(host):
    """
    Returns the current user for the given host.

    :param host: Host to fetch the current for.

    :returns: The current user for this host or None if not set.
    """
    # Retrieve the cached info file location from the host
    info_path = _get_site_authentication_file_location(host)
    document = _try_load_site_authentication_file(info_path)
    user = document[_CURRENT_USER]
    logger.debug("Current user is '%s'" % user)
    return user.strip() if user else user


def set_current_user(host, login):
    """
    Saves the current user for a given host.

    :param host: Host to save the current user for.
    :param login: The current user login for specified host.
    """
    host = host.strip()
    login = login.strip()

    file_path = _get_site_authentication_file_location(host)
    _ensure_folder_for_file(file_path)

    current_user_file = _try_load_site_authentication_file(file_path)
    current_user_file[_CURRENT_USER] = login
    _write_yaml_file(file_path, current_user_file)


def get_current_cookies(host):
    """
    Returns the current user for the given host.

    :param host: Host to fetch the current for.

    :returns: The current user for this host or None if not set.
    """
    # Retrieve the cached info file location from the host
    info_path = _get_site_authentication_file_location(host)
    document = _try_load_site_authentication_file(info_path)
    cookies = document[_CURRENT_COOKIES]
    logger.debug("Current cookies are '%s'" % cookies)
    return cookies


def set_current_cookies(host, login, cookies):
    """
    Saves the current user for a given host.

    :param host: Host to save the current user for.
    :param login: The current user login for specified host.
    """
    host = host.strip()
    login = login.strip()

    file_path = _get_site_authentication_file_location(host)
    _ensure_folder_for_file(file_path)

    current_user_file = _try_load_site_authentication_file(file_path)
    current_user_file[_CURRENT_COOKIES] = cookies
    _write_yaml_file(file_path, current_user_file)


def get_current_host():
    """
    Returns the current host.

    :returns: The current host string, None if undefined
    """
    # Retrieve the cached info file location from the host
    info_path = _get_global_authentication_file_location()
    document = _try_load_global_authentication_file(info_path)
    host = document[_CURRENT_HOST]
    logger.debug("Current host is '%s'" % host)
    return host


def set_current_host(host):
    """
    Saves the current host.

    :param host: The new current host.
    """
    file_path = _get_global_authentication_file_location()
    _ensure_folder_for_file(file_path)

    current_host_file = _try_load_global_authentication_file(file_path)
    current_host_file[_CURRENT_HOST] = host.strip()
    _write_yaml_file(file_path, current_host_file)

@LogManager.log_timing
def generate_session_token(hostname, login, password, http_proxy, auth_token=None):
    """
    Generates a session token for a given username/password on a given site.

    :param hostname: The host to connect to.
    :param login: The user to get a session for.
    :param password: Password for the user.
    :param http_proxy: Proxy to use. Can be None.
    :param auth_token: Two factor authentication token for the user. Can be None.

    :returns: The generated session token for that user/password/auth_token/site combo.

    :raises AuthenticationError: Raised when the user information is invalid.
    :raises MissingTwoFactorAuthenticationFault: Raised when missing a two factor authentication
        code or backup code.
    :raises Exception: Raised when a network error occurs.
    """
    try:
        # Create the instance that does not connect right away for speed...
        logger.debug("Connecting to Shotgun to generate session token...")
        sg = Shotgun(
            hostname,
            login=login,
            password=password,
            http_proxy=http_proxy,
            connect=False,
            auth_token=auth_token
        )
        # .. and generate the session token. If it throws, we have invalid
        # credentials or invalid host/proxy settings.
        return sg.get_session_token()
    except AuthenticationFault:
        raise AuthenticationError("Authentication failed.")
    except (ProtocolError, httplib2.ServerNotFoundError):
        raise AuthenticationError("Server %s was not found." % hostname)
    # In the following handlers, we are not rethrowing an AuthenticationError for
    # a very specific reason. While wrong credentials or host is a user
    # recoverable error, problems with proxy settings or network errors are much
    # more severe errors which can't be fixed by reprompting. Therefore, they have
    # nothing to do with authentication and shouldn't be reported as such.
    except socket.error, e:
        logger.exception("Unexpected connection error.")
        # e.message is always an empty string, so look at the exception's arguments.
        # The arguments are always a string or a number and a string.
        if isinstance(e.args[0], str):
            # if the error is just a string, simply forward the message.
            raise Exception(e.args[0])
        else:
            # We could argue here that we should only display the string portion of the
            # error since the error code is of little relevance to the user, but since
            # Toolkit doesn't properly log everything to a file at the moment, it's probably
            # safer to have the error code a little bit more in the open. Also, the formatting
            # of this exception type is pretty bad so let's reformat it ourselves. By default, it
            # turns a tuple into a string.
            raise Exception("%s (%d)" % (e.args[1], e.args[0]))
    except httplib2.socks.ProxyError, e:
        logger.exception("Unexpected connection error.")
        # Same comment applies here around formatting.
        # Note that e.message is always a tuple in this
        raise Exception("%s (%d)" % (e.message[1], e.message[0]))
    except MissingTwoFactorAuthenticationFault:
        # Silently catch and rethrow to avoid logging.
        raise
    except Exception, e:
        logger.exception("There was a problem logging in.")
        # If the error message is empty, like httplib.HTTPException, convert
        # the class name to a string
        if len(str(e)) == 0:
            raise Exception("Unknown error: %s" % type(e).__name__)
        else:
            raise
