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
--------------------------------------------------------------------------------
NOTE! This module is part of the authentication library internals and should
not be called directly. Interfaces and implementation of this module may change
at any point.
--------------------------------------------------------------------------------
"""

from tank_vendor.shotgun_api3 import Shotgun, AuthenticationFault
from tank_vendor.shotgun_api3.lib.xmlrpclib import ProtocolError
from . import interactive_authentication, session_cache
from .. import LogManager

from pprint import pprint

logger = LogManager.get_logger(__name__)

class ShotgunWrapper(Shotgun):
    """
    This class wraps the Shotgun instance that communicates with the Shotgun
    server. Every time a request is made to the server and we are authenticated
    as a session user, the call will be monitored for an AuthenticationFault.
    If it happens, the call will be interrupted by a prompt asking for the user's
    password to renew the session. Once the session is renewed, the call will be
    executed again.
    """
    def __init__(self, *args, **kwargs):
        """
        Constructor. This has the same parameters as the Shotgun class, but it
        has an extra sg_auth_user parameter documented below.

        :param sg_auth_user: ShotgunUser derived instance that represents the
                             authenticated user making the request.
        """
        self._user = kwargs["sg_auth_user"]
        del kwargs["sg_auth_user"]
        super(ShotgunWrapper, self).__init__(*args, **kwargs)

    # def _make_call(self, *args, **kwargs):
    #     http_status, resp_headers, body = super(ShotgunWrapper, self)._make_call(*args, **kwargs)
    #     print "\n\n\nMY _make_call"
    #     pprint(resp_headers)
    #     print "\n\n\n"
    #     return http_status, resp_headers, body

    def _call_rpc(self, *args, **kwargs):
        """
        Wraps the _call_rpc method from the base class to trap authentication
        errors and prompt for the user's password.
        """

        # print "\n\n\n_call_rpc\n\n\n"
        try:
            # If the user's session token has changed since we last tried to
            # call the server, it's because the token expired and there's a
            # new one available, so use that one instead in the future.
            if self._user.get_session_token() != self.config.session_token:
                logger.debug("Global session token has changed. Using that instead.")
                self.config.session_token = self._user.get_session_token()

            return super(ShotgunWrapper, self)._call_rpc(*args, **kwargs)
        except AuthenticationFault:
            logger.debug("Authentication failure.")
            pass
        except ProtocolError as e:
            if e.errcode == 302 and e.headers.has_key('location'):
                pass
            else:
                raise e
            # from pprint import pprint
            # print "--->"
            # print dir(e)
            # print "<---: %s:%s" % (type(e.errcode), e.errcode)
            # pprint(e.headers)
            # print "<---"
            # pass

        # Before renewing the session token, let's see if there is another
        # one in the session_cache.
        session_info = session_cache.get_session_data(self._user.get_host(), self._user.get_login())

        # If the one if the cache is different, maybe another process refreshed the token
        # for us, let's try that token instead.
        if session_info and session_info["session_token"] != self._user.get_session_token():
            logger.debug("Different session token found in the session cache. Will try it.")
            self.config.session_token = session_info["session_token"]
            # Try again. If it fails with an authentication fault, that's ok
            try:
                result = super(ShotgunWrapper, self)._call_rpc(*args, **kwargs)
                # It didn't fail, so we can update the session token for the user. The value is
                # coming from the cache, so we should avoid an unnecessary write to disk.
                logger.debug("Cached token was not expired. Saving to memory.")
                self._user.set_session_token(session_info["session_token"], cache=False)
                return result
            except AuthenticationFault:
                logger.debug("Authentication failure, cached token was also expired.")
                pass

        # We end up here if we were in sync with the cache or if tried the cached value but it
        # didn't work.

        # Let's renew the session token!
        interactive_authentication.renew_session(self._user)
        self.config.session_token = self._user.get_session_token()
        #  If there is once again an authentication fault, then it means
        # something else is going wrong and we will then simply rethrow
        return super(ShotgunWrapper, self)._call_rpc(*args, **kwargs)
