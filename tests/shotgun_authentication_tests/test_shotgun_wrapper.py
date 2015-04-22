# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import with_statement
from mock import patch

from tank_test.tank_test_base import *

from tank_vendor.shotgun_api3 import AuthenticationFault
from tank_vendor.shotgun_authentication import user, ShotgunAuthenticationError


class ShotgunWrapperTests(TankTestBase):
    """
    Tests the user module. Note that because how caching the session information is still
    very much in flux, we will not be unit testing cache_session_info, get_session_data and
    delete_session_data for now, since they have complicated to test and would simply slow us down.
    """

    @patch("tank_vendor.shotgun_api3.Shotgun._call_rpc")
    @patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    @patch("tank_vendor.shotgun_authentication.interactive_authentication.renew_session")
    def test_create_connection_with_session_renewal(self, renew_session_mock, server_caps_mock, _call_rpc_mock):
        """
        When there is no valid session cached, the engine's renew session should take care of the
        session renewal
        """

        mocked_result = {"entities": [1, 2, 3]}
        _call_rpc_mock.side_effect = AuthenticationFault()

        sg_user = user.SessionUser("https://host.shotgunstudio.com", "login", "session", "proxy")
        # Directly call _call_rpc. We should be invoking the derived class here, which will
        # then invoke the base class which is in fact our mock class so it should throw once and then
        # succeed.

        # Make sure that when renewing the session that we update the mock so that the next time _call_rpc
        # is called we don't throw anything.
        def renew_session_side_effect(*args, **kwargs):
            _call_rpc_mock.side_effect = [mocked_result]

        renew_session_mock.side_effect = renew_session_side_effect
        test_result = sg_user.create_sg_connection()._call_rpc()

        # Make sure we tried to renew the sesion
        self.assertTrue(renew_session_mock.called)
        # Make sure _call_rpc was called twice
        self.assertEqual(_call_rpc_mock.call_count, 2)
        self.assertEqual(id(mocked_result), id(test_result))

    @patch("tank_vendor.shotgun_api3.Shotgun._call_rpc")
    @patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    @patch("tank_vendor.shotgun_authentication.interactive_authentication.renew_session")
    def test_create_connection_with_session_renewal_failure(self, renew_session_mock, server_caps_mock, _call_rpc_mock):
        """
        When there is no valid session cached, the engine's renew session should take care of the
        session renewal, but if the session renewal failed, we should get an AuthenticationFault as
        before.
        """

        _call_rpc_mock.side_effect = AuthenticationFault("This is coming from the _call_rpc_mock.")
        renew_session_mock.side_effect = ShotgunAuthenticationError("This is coming from renew_session_mock.")

        sg_user = user.SessionUser("https://host.shotgunstudio.com", "login", "session", "proxy")
        with self.assertRaisesRegexp(ShotgunAuthenticationError, "This is coming from renew_session_mock."):
            sg_user.create_sg_connection()._call_rpc()

        # Make sure we tried to renew the sesion
        self.assertTrue(renew_session_mock.called)
        self.assertEqual(_call_rpc_mock.call_count, 1)
