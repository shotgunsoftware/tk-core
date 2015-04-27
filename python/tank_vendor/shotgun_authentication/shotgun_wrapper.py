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
        try:
            return super(ShotgunWrapper, self)._call_rpc(*args, **kwargs)
        except AuthenticationFault:
            interactive_authentication.renew_session(self._user)
            self.config.session_token = self._user.get_session_token()
            #  If there is once again an authentication fault, then it means
            # something else is going wrong and we will then simply rethrow
            return super(ShotgunWrapper, self)._call_rpc(*args, **kwargs)
