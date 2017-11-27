# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import threading
import time

from . import interactive_authentication
from . import user_impl
from . import shotgun_shared
from .. import LogManager
from .errors import AuthenticationCancelled


logger = LogManager.get_logger(__name__)

# Ensure that the SSO-related logging will be merged in our loggin.
shotgun_shared.set_logger_parent(logger)


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
        self._impl.refresh_credentials()

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


class ShotgunSamlUser(ShotgunUser):
    """
    This specialized shotgun user is needed when SSO is used, as it provides
    mechanisms for automatic claims renewal.

    User objects are created via the :class:`ShotgunAuthenticator` object, which will handle
    caching user objects on disk, prompting the user for their credentials etc.

    This specialized class allows the user to query the claims expiration and
    see if `interactive_authentication.renew_session(user)` needs to be called.

    It is also possible to start/stop/query the state of the automatic claims renewal:

        user = ...
        if isinstance(user, ShotgunSamlUser):
            user.start_claims_renewal()
        ...
        if user.is_claims_renewal_active():
            user.stop_claims_renewal()
    """

    def __init__(self, impl):
        """
        :param impl: Internal user implementation class this class proxies.
        """
        super(ShotgunSamlUser, self).__init__(impl)
        self._timer = None

    def get_claims_expiration(self):
        """
        Obtain claims expiration for the user.

        :returns: The expiration in seconds since January 1st 1970 UTC.
        """
        return shotgun_shared.get_saml_claims_expiration(self._impl.get_cookies())

    def _do_automatic_claims_renewal(self, preemtive_renewal_threshold=0.9):
        """
        Handles automatic renewal of the SAML2 claims for the user.

        :params user: an already logged in user.
        :params preemtive_renewal_threshold: How far into the claims duration we will attempt renewal.
                                             Defaults to 90%, usually 3 minutes 45 seconds (90% of 5 mins).
        """
        logger.debug("Attempting automatic claims renewal")
        try:
            previous_expiration = self.get_claims_expiration()
            # A call to renew_session when SSO is used will not prompt the user for
            # their credentials if it is not necessary.
            interactive_authentication.renew_session(self._impl)
            new_expiration = self.get_claims_expiration()

            if new_expiration > previous_expiration:

                logger.debug("Automatic claims renewal succeeded.")
                delta = (new_expiration - time.time()) * preemtive_renewal_threshold
                # If we are debugging, we will use a shorter expiration time.
                # SHOTGUN_SSO_RENEWAL_INTERVAL should be a value in seconds.
                if "SHOTGUN_SSO_RENEWAL_INTERVAL" in os.environ:
                    delta = int(os.environ["SHOTGUN_SSO_RENEWAL_INTERVAL"])
                logger.debug("Next claims renewal attempt: %f" % delta)
                self._timer = threading.Timer(delta, self._do_automatic_claims_renewal, [preemtive_renewal_threshold])
                self._timer.start()
            else:
                logger.warning("No further attempts to auto-renew in the background will be attempted.")
        except AuthenticationCancelled:
            logger.debug("Automatic SSO claim renewal was cancelled while processing.")
            raise

    def start_claims_renewal(self, preemtive_renewal_threshold=0.9):
        """
        Start claims renewal mechanism.
        """
        if self._timer is None or not self.is_claims_renewal_active():
            self._do_automatic_claims_renewal(preemtive_renewal_threshold)
        else:
            logger.debug("Attempting to start claims renewal when it was already active.")

    def stop_claims_renewal(self):
        """
        Stops claims renewal mechanism.
        """
        if self._timer:
            self._timer.cancel()
        else:
            logger.debug("Attempting to stop claims renewal when it was not active.")

    def is_claims_renewal_active(self):
        """
        Query the current state of the claims renewal mechanism.

        :returns: A bool value on the current active state of the renewal loop.
        """
        if self._timer:
            return self._timer.is_alive()
        else:
            return False


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
    impl = user_impl.deserialize_user(payload)

    # We use the presence of cookies as an indicator that we are using SSO.
    if isinstance(impl, user_impl.SessionUser) and impl.get_cookies() is not None:
        return ShotgunSamlUser(impl)
    else:
        return ShotgunUser(impl)
