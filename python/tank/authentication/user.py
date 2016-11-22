# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from . import user_impl


class ShotgunUser(object):
    """
    Represents a Shotgun user, either a script or a person and provides an entry point
    into the authentication system.

    User objects are created via the :class:`ShotgunAuthenticator` object, which will handle
    caching user objects on disk, prompting the user for their credentials etc.

    Once you have retrieved one of the user objects below, this can be used to access
    Shotgun in a seamless way. The :meth:`create_sg_connection()` will return a Shotgun API handle
    which is associated with the current user. This API handle is also monitored for
    authentication timeouts, so if the user's session times out (typically due to periods
    of inactivity), the user may be prompted (via a QT UI or stdin/stdout if only
    console is accessible) to refresh their Shotgun session by typing in their password.

    If you need to persist the user object, this is possible via the serialization
    methods. This is particularly useful if you need to pass a user object from one
    process to another, for example when launching a DCC such as Maya or Nuke.
    """

    def __init__(self, impl):
        """
        :param impl: Internal user implementation class this class proxies.
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
        return self._impl.get_http_proxy()

    @property
    def login(self):
        """
        The login for this current user. For Shotgun user types that don't have a concept
        of a login (like API scripts), None is returned.

        :returns: The login string or None.
        """
        return self._impl.get_login()

    @property
    def cookies(self):
        """
        The cookies for this current user. For Shotgun user types that don't have a concept
        of a login (like API scripts), and empty list is returned.

        :returns: A list, potentially empty, of cookies.
        """
        return self._impl.get_cookies()

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

    def __str__(self):
        """
        Returns the name of the user.

        :returns: The user's name string.
        """
        return str(self.impl)

    def __repr__(self):
        """
        Returns a string representation of the user.

        :returns: A string representation of the user.
        """
        return repr(self.impl)

    @property
    def impl(self):
        """
        Returns the user implementation object. Note: Retrieving the implementation
        object is unsupported and should not be attempted. It is there to expose
        functionality to the internals of the authentication module. We
        reserve the right to alter the interface of the implementation object
        as it needs to.

        :returns: The ShotgunUserImpl derived object.
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

    :param payload: Pickled dictionary of values

    :returns: A ShotgunUser derived instance.
    """
    return ShotgunUser(user_impl.deserialize_user(payload))
