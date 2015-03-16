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
Provides shorthand versions of all public methods on the AuthenticationManager. Useful
when mocking for unit test without having to worry to mock the most derived class.
"""

from .authentication_manager import AuthenticationManager


def is_human_user_authenticated(connection_information):
    """
    Indicates if we are authenticating with a user.
    :param connection_information: Information used to connect to Shotgun.
    :returns: True is we are using a session, False otherwise.
    """
    return AuthenticationManager.get_instance().is_human_user_authenticated(connection_information)


def get_host():
    """
    Returns the current host.
    :returns: A string with the hostname.
    """
    return AuthenticationManager.get_instance().get_host()


def get_http_proxy():
    """
    Returns the optional http_proxy.
    :returns: A string with the hostname of the proxy. Can be None.
    """
    return AuthenticationManager.get_instance().get_http_proxy()


def get_credentials():
    """
    Retrieves the credentials for the current user.
    :returns: A dictionary holding the credentials that were found. Can either contains keys:
              - login, session_token
              - an empty dictionary.
              The dictionary will be empty if no credentials were found.
    """
    return AuthenticationManager.get_instance().get_credentials()


def get_connection_information():
    """
    Returns a dictionary with connection parameters and user credentials.
    :returns: A dictionary with keys host, http_proxy and all the keys returned from get_credentials.
    """
    return AuthenticationManager.get_instance().get_connection_information()


def logout():
    """
    Logs out of the currently cached session.
    :returns: The connection information before it was cleared if logged in, None otherwise.
    """
    return AuthenticationManager.get_instance().logout()


def is_authenticated():
    """
    Indicates if we need to authenticate.
    :returns: True is we are authenticated, False otherwise.
    """
    return AuthenticationManager.get_instance().is_authenticated()


def clear_cached_credentials():
    """
    Clears any cached credentials.
    """
    return AuthenticationManager.get_instance().clear_cached_credentials()


def cache_connection_information(host, login, session_token):
    """
    Caches authentication credentials.
    :param host: Host to cache.
    :param login: Login to cache.
    :param session_token: Session token to cache.
    """
    return AuthenticationManager.get_instance().cache_connection_information(host, login, session_token)
