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
Exposes information about a user.
"""

from . import user_impl


class ShotgunUser(object):
    """
    Shotgun user class. It exposes information about the user.
    """
    def __init__(self, impl):
        """
        Constructor.

        :param impl: User implementation class this class proxies.
        """

        self._impl = impl

    @property
    def host(self):
        """
        Returns the host for this user.

        :returns: The host string.
        """
        return self._impl.get_host()

    @property
    def http_proxy(self):
        """
        Returns the HTTP proxy for this user.

        :returns: The HTTP proxy string.
        """
        return self._impl.get_host()

    @property
    def login(self):
        """
        The login for this current user.

        :returns: The login string. If None, this user has no login associated
            to it.
        """
        if isinstance(self._impl, user_impl.SessionUser):
            return self._impl.get_login()
        else:
            return None

    def create_sg_connection(self):
        """
        Creates a Shotgun connection using the credentials for this user.

        :returns: A Shotgun connection.
        """
        return self._impl.create_sg_connection()

    def are_credentials_expired(self):
        """
        Checks if the credentials for the user are expired.

        :returns: True if the credentials are expired, False otherwise.
        """
        return self._impl.are_credentials_expired()

    def refresh_credentials(self):
        """
        Refreshes the credentials of this user so that they don't expire.
        If they are expired, you will be prompted for the user's password.
        """
        # Make a very simple authenticated request that returns as little information as possible.
        # If the session token was expired, the ShotgunWrapper returned by create_sg_connection
        # will take care of the session renewal.
        self.create_sg_connection().find_one("HumanUser", [])

    @property
    def impl(self):
        """
        Returs the user implementation object. Note: Retrieving the implementation
        object is unsupported and should not be attempted. It is there to expose
        functionality to the internals of the authentication module. Autodesk
        reserves the right to alter the interface of the implementation object
        as it needs to.

        :returns: The ShotgunUserImpl dervied object.
        """
        return self._impl


def serialize_user(user):
    """
    Serializes a user. Meant to be consumed by deserialize.

    :param user: User object that needs to be serialized.

    :returns: The payload representing the user.
    """
    return user_impl.serialize_user(user.impl)


def deserialize_user(payload):
    """
    Converts a payload produced by serialize into any of the ShotgunUser
    derived instance.

    :params payload: Pickled dictionary of values

    :returns: A ShotgunUser derived instance.
    """
    return ShotgunUser(user_impl.deserialize_user(payload))
