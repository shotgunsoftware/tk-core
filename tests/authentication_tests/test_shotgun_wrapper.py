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

from tank_test.tank_test_base import ShotgunTestBase
from tank_test.tank_test_base import setUpModule # noqa


from tank_vendor.shotgun_api3 import AuthenticationFault
from tank.authentication import user_impl, ShotgunAuthenticationError


class ShotgunWrapperTests(ShotgunTestBase):
    """
    Tests the user_impl module.
    """

    @patch("tank_vendor.shotgun_api3.Shotgun._call_rpc")
    @patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    @patch("tank.authentication.interactive_authentication.renew_session")
    def test_create_connection_with_session_renewal(self, renew_session_mock, server_caps_mock, _call_rpc_mock):
        """
        When there is no valid session cached, the engine's renew session should take care of the
        session renewal
        """

        mocked_result = {"entities": [1, 2, 3]}
        _call_rpc_mock.side_effect = AuthenticationFault()

        user = user_impl.SessionUser("https://host.shotgunstudio.com", "login", "session", "proxy")
        # Directly call _call_rpc. We should be invoking the derived class here, which will
        # then invoke the base class which is in fact our mock class so it should throw once and then
        # succeed.

        # Make sure that when renewing the session that we update the mock so that the next time _call_rpc
        # is called we don't throw anything.
        def renew_session_side_effect(*args, **kwargs):
            _call_rpc_mock.side_effect = [mocked_result]

        renew_session_mock.side_effect = renew_session_side_effect
        test_result = user.create_sg_connection()._call_rpc()

        # Make sure we tried to renew the sesion
        self.assertTrue(renew_session_mock.called)
        # Make sure _call_rpc was called twice
        self.assertEqual(_call_rpc_mock.call_count, 2)
        self.assertEqual(id(mocked_result), id(test_result))

    @patch("tank_vendor.shotgun_api3.Shotgun._call_rpc")
    @patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    @patch("tank.authentication.interactive_authentication.renew_session")
    def test_create_connection_with_session_renewal_failure(self, renew_session_mock, server_caps_mock, _call_rpc_mock):
        """
        When there is no valid session cached, the engine's renew session should take care of the
        session renewal, but if the session renewal failed, we should get an AuthenticationFault as
        before.
        """

        _call_rpc_mock.side_effect = AuthenticationFault("This is coming from the _call_rpc_mock.")
        renew_session_mock.side_effect = ShotgunAuthenticationError("This is coming from renew_session_mock.")

        user = user_impl.SessionUser("https://host.shotgunstudio.com", "login", "session", "proxy")
        with self.assertRaisesRegexp(ShotgunAuthenticationError, "This is coming from renew_session_mock."):
            user.create_sg_connection()._call_rpc()

        # Make sure we tried to renew the sesion
        self.assertTrue(renew_session_mock.called)
        self.assertEqual(_call_rpc_mock.call_count, 1)

    @patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    @patch("tank.authentication.interactive_authentication.renew_session")
    @patch("tank.authentication.session_cache.get_session_data")
    @patch("tank_vendor.shotgun_api3.Shotgun._call_rpc")
    def test_successfull_session_cache_snooping(self, _call_rpc_mock, get_session_data_mock, renew_session_mock, server_caps_mock):
        """
        Tests that if the session token is invalid (mocked by the _call_rpc mocker), that we will try to
        get the session token from disk first before trying to renew the session token.
        """

        # First create the user and the connection object
        user = user_impl.SessionUser("https://host.shotgunstudio.com", "login", "session_token", "proxy")
        connection = user.create_sg_connection()

        # Mock a call to the server that fails authentication.
        _call_rpc_mock.side_effect = AuthenticationFault("This is coming from the _call_rpc_mock.")

        # Implement a fake get_session_data that returns the required information.
        def fake_get_session_data(*args):
            # Disable the mock side effect so that the next time the method is called all is well.
            _call_rpc_mock.side_effect = None
            return {"login": "login", "session_token": "session_token_2"}
        get_session_data_mock.side_effect = fake_get_session_data

        # This should:
        # - Call the RPC and throw because of the mock
        # - Look into the session cache is the session token changed (it did, fake_get_session_data returns session_token_2)
        # - Call the RPC again and not throw (since there is no side effect this time)
        connection._call_rpc()

        # We should look in the cache once.
        self.assertEqual(get_session_data_mock.call_count, 1)
        # We shouldn't try to renew the session.
        self.assertFalse(renew_session_mock.called)
        # We should have talked to the server twice.
        self.assertEqual(_call_rpc_mock.call_count, 2)

    @patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    @patch("tank.authentication.interactive_authentication.renew_session")
    @patch("tank.authentication.session_cache.get_session_data")
    @patch("tank_vendor.shotgun_api3.Shotgun._call_rpc")
    def test_failed_session_cache_snooping(self, _call_rpc_mock, get_session_data_mock, renew_session_mock, server_caps_mock):
        """
        Tests that if the session token is invalid (mocked by the _call_rpc mocker), that the session cache
        has been read, did provide an update and wasn't the right one, that we would renew the session.
        """

        # First create the user and the connection object
        user = user_impl.SessionUser("https://host.shotgunstudio.com", "login", "session_token", "proxy")
        connection = user.create_sg_connection()

        # Mock a call to the server that fails authentication.
        _call_rpc_mock.side_effect = AuthenticationFault("This is coming from the _call_rpc_mock.")

        # Implement a fake get_session_data that returns the required information.
        def fake_get_session_data(*args):
            return {"login": "login", "session_token": "session_token_2"}
        get_session_data_mock.side_effect = fake_get_session_data

        def fake_renew_session(*args):
            _call_rpc_mock.side_effect = None

        renew_session_mock.side_effect = fake_renew_session

        # This should:
        # - Call the RPC and throw because of the mock
        # - Look into the session cache is the session token changed (it did, fake_get_session_data returns session_token_2)
        # - Call the RPC again and fail again since there the session token is still invalid (simulated bu the mock)
        # - Call get_session_data a second time.
        connection._call_rpc()

        # We should look in the cache once.
        self.assertEqual(get_session_data_mock.call_count, 1)
        # We shouldn't try to renew the session.
        self.assertTrue(renew_session_mock.called)
        # We should have talked to the server twice.
        self.assertEqual(_call_rpc_mock.call_count, 3)
