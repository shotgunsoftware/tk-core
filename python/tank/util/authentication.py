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

import logging

from tank_vendor.shotgun_api3 import Shotgun
from tank_vendor.shotgun_api3.lib import httplib2
from tank_vendor.shotgun_api3 import AuthenticationFault, ProtocolError
from tank.errors import TankAuthenticationError

from .authentication_manager import AuthenticationManager

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


def _is_session_token_cached():
    """
    Returns if there is a cached session token for the current user.
    :returns: True is there is, False otherwise.
    """
    if _is_human_user_authenticated(get_connection_information()):
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
    if authentication_data.get("api_script") and authentication_data.get("api_key"):
        # we have non-null data for script credentials
        return True
    else:
        return False


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
    return _is_human_user_authenticated(get_connection_information())


def is_authenticated():
    """
    Indicates if we need to authenticate.
    :returns: True is we are using a script user or have a valid session token, False otherwise.
    """
    authentication_data = get_connection_information()
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


def _create_sg_connection_from_session(connection_information):
    """
    Tries to auto login to the site using the existing session_token that was saved.
    :param connection_information: Authentication credentials.
    :returns: Returns a Shotgun instance.
    """
    logger.debug("Trying to auto-login")

    if "login" not in connection_information or "session_token" not in connection_information:
        logger.debug("Nothing was cached.")
        return None

    # Try to refresh the data
    logger.debug("Validating token.")

    sg = _validate_session_token(
        connection_information["host"],
        connection_information["session_token"],
        connection_information.get("http_proxy")
    )
    if sg:
        logger.debug("Token is still valid!")
        return sg
    else:
        # Session token was invalid, so uncache it to make sure nobody else tries using it.
        clear_cached_credentials()
        logger.debug("Failed refreshing the token.")
        return None


def create_sg_connection_from_script_user(connection_information):
    """
    Create a Shotgun connection based on a script user.
    :param connection_information: A dictionary with keys host, api_script, api_key and an optional http_proxy.
    :returns: A Shotgun instance.
    """
    return _shotgun_instance_factory(
        connection_information["host"],
        script_name=connection_information["api_script"],
        api_key=connection_information["api_key"],
        http_proxy=connection_information.get("http_proxy", None)
    )


def create_authenticated_sg_connection():
    """
    Creates an authenticated Shotgun connection.
    :param config_data: A dictionary holding the site configuration.
    :returns: A Shotgun instance.
    """
    connection_information = get_connection_information()
    # If no configuration information
    if _is_script_user_authenticated(connection_information):
        # create API
        return create_sg_connection_from_script_user(connection_information)
    else:
        return _create_or_renew_sg_connection_from_session(connection_information)


def logout():
    """
    Logs out of the currently cached session.
    :returns: True is logging out was successful, False is no session was cached.
    """
    if _is_session_token_cached():
        clear_cached_credentials()
        return True
    else:
        return False


# Shothands for AuthenticationManager.get_instance().xxx

def get_connection_information():
    """
    Retrieves the authentication credentials.
    :returns: A dictionary with credentials to connect to a site. If the authentication is made using
              a script user, a dictionary with the following keys will be returned: host, api_script, api_key.
              If the authentication is made using a human user, a dictionary with the following keys will
              be returned: host, login, session_token. In both cases, an optional http_proxy entry can be present.
    """
    return AuthenticationManager.get_instance().get_connection_information()


def clear_cached_credentials():
    """
    Clears cached credentials.
    """
    AuthenticationManager.get_instance().clear_cached_credentials()


def cache_connection_information(host, login, session_token):
    """
    Caches authentication credentials.
    :param host: Host to cache.
    :param login: Login to cache.
    :param session_token: Session token to cache.
    """
    AuthenticationManager.get_instance().cache_connection_information(host, login, session_token)


