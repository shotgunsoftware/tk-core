# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from tank_vendor.shotgun_api3 import Shotgun, AuthenticationFault
from . import interactive_authentication


class ShotgunWrapper(Shotgun):
    """
    This class wraps the Shotgun instance that communicates with the Shotgun
    server. Everytime a request is made to the server and we are authenticated
    as a session user, the call will be monitored for an AuthenticationFault.
    If it happens, the call will be interupted by a prompt asking for the user's
    password to renew the session. Once the session is renewed, the call will be
    executed again.
    """
    def __init__(self, *args, **kwargs):
        """
        Constructor. This has the same parameters as the Shotgun class, but it
        has an extra nmed parameter documented below.

        :param user: ShotgunUser derived instance that represents the
                     authenticated user making the request.
        """
        self._user = kwargs["user"]
        del kwargs["user"]
        super(ShotgunWrapper, self).__init__(*args, **kwargs)

    def _call_rpc(self, *args, **kwargs):
        """
        Wraps the _call_rpc method from the base class to trap authentication
        errors and prompt for the user's password.
        """
        # If we have a script user, there's nothing special to do.
        from . import user
        if user.is_script_user(self._user):
            return super(ShotgunWrapper, self)._call_rpc(*args, **kwargs)

        # Capture the current value of the session token. This is not
        # thread-safe, but it doesn't matter at this point. Let's go through the
        # scenarios.
        #
        # 1) This is the only thread that reads the session token. Nothing to
        #    worry about.
        # 2) Two threads read this value, and both end up in the exception
        #    handler. The first one will take the lock in renew_session while
        #    the other will wait. Once the first once updates the session token
        #    on the user, unlocks and the second thread gets the lock, the
        #    comparison will show that the token did indeed get updated and will
        #    unlock with asking for credentials.
        # 3) One thread gets the authentication error and goes as far as updating
        #    self.config.session_token, but not before another thread has
        #    initialized original session token with the old value. Since
        #    self.config.session_token is now valid at the time of the
        #    _call_rpc call, there is no problem.

        original_session_token = self.config.session_token
        try:
            return super(ShotgunWrapper, self)._call_rpc(*args, **kwargs)
        except AuthenticationFault:
            interactive_authentication.renew_session(self._user, original_session_token)
            self.config.session_token = self._user.get_session_token()
            #  If there is once again an authentication fault, then it means
            # something else is going wrong and we will then simply rethrow
            return super(ShotgunWrapper, self)._call_rpc(*args, **kwargs)
