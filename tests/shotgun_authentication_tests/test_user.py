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
import tank_test
from tank_test import mockgun

from tank_vendor.shotgun_authentication import user, AuthenticationError
from tank_vendor.shotgun_api3 import shotgun


class AuthenticationTests(TankTestBase):
    """
    Tests the user module. Note that because how caching the session information is still
    very much in flux, we will not be unit testing cache_session_info, get_session_data and
    delete_session_data for now, since they have complicated to test and would simply slow us down.
    """

    @patch("tank_vendor.shotgun_authentication.user.SessionUser._create_sg_connection")
    def test_create_from_valid_session(self, create_sg_connection_mock):
        """
        When cache info is valid and _create_sg_connection succeeds, it's return value
        is returned by create_sg_connection.
        """
        # The return value of the _validate_session_token is also the return value of
        # _create_sg_connection_from_session. Make sure we are getting it.
        create_sg_connection_mock.return_value = "Success"
        sg_user = user.SessionUser("host", "login", "session", "proxy", is_volatile=False)
        self.assertEqual(sg_user.create_sg_connection(), "Success")

    @patch("tank_test.mockgun.Shotgun.find_one")
    @patch("tank_vendor.shotgun_authentication.user._shotgun_instance_factory")
    def test_authentication_failure_in_validate_session_token(self, shotgun_instance_factory_mock, find_one_mock):
        """
        In _create_sg_connection, if find_one throws AuthenticationFault exception, we should
        fail gracefully
        """
        shotgun_instance_factory_mock.side_effect = tank_test.mockgun.Shotgun
        # find_one should throw the AuthenticationFault, which should gracefully abort connecting
        # to Shotgun
        find_one_mock.side_effect = shotgun.AuthenticationFault
        sg_user = user.SessionUser("host", "login", "session", "proxy", is_volatile=False)
        self.assertEquals(sg_user._create_sg_connection(), None)

    @patch("tank_test.mockgun.Shotgun.find_one")
    @patch("tank_vendor.shotgun_authentication.user._shotgun_instance_factory")
    def test_unexpected_failure_in_validate_session_token(self, shotgun_instance_factory_mock, find_one_mock):
        """
        In _create_sg_connection, if find_one throws anything else than AuthenticationFault, it
        should be rethrown.
        """
        shotgun_instance_factory_mock.side_effect = tank_test.mockgun.Shotgun

        class ExceptionThatShouldPassRightThrough(Exception):
            pass
        # Any other error type than AuthenticationFailed is unexpected and should be rethrown
        find_one_mock.side_effect = ExceptionThatShouldPassRightThrough
        sg_user = user.SessionUser("host", "login", "session", "proxy", is_volatile=False)
        with self.assertRaises(ExceptionThatShouldPassRightThrough):
            sg_user.create_sg_connection()

    @patch("tank_vendor.shotgun_authentication.user.SessionUser._create_sg_connection")
    @patch("tank_vendor.shotgun_authentication.interactive_authentication.renew_session")
    def test_create_connection_with_session_renewal(self, renew_session_mock, create_sg_connection_mock):
        """
        When there is no valid session cached, the engine's renew session should take care of the
        session renewal
        """

        new_connection = mockgun.Shotgun("https://something.shotgunstudio.com")
        # First call will fail creating something from the cache, and the second call will be the 
        # after we renwed the session.
        create_sg_connection_mock.side_effect = [None, new_connection]
        renew_session_mock.return_value = None

        sg_user = user.SessionUser("host", "login", "session", "proxy", is_volatile=False)
        result = sg_user.create_sg_connection()

        # Make sure we tried to renew the sesion
        self.assertTrue(renew_session_mock.called)
        self.assertEqual(create_sg_connection_mock.call_count, 2)
        self.assertEqual(id(result), id(new_connection))

    @patch("tank_vendor.shotgun_authentication.user.SessionUser._create_sg_connection")
    @patch("tank_vendor.shotgun_authentication.interactive_authentication.renew_session")
    def test_create_connection_with_session_renewal_failure(self, renew_session_mock, create_sg_connection_mock):
        """
        When there is no valid session cached, the engine's renew session should take care of the
        session renewal, but if the session renewal failed, we should get a AuthenticationError
        """
        # Always fail creating a cached session
        create_sg_connection_mock.return_value = None
        renew_session_mock.return_value = None

        sg_user = user.SessionUser("host", "login", "session", "proxy", is_volatile=False)
        with self.assertRaisesRegexp(AuthenticationError, "failed"):
            sg_user.create_sg_connection()

        # Make sure we tried to renew the sesion
        self.assertTrue(renew_session_mock.called)
        self.assertEqual(create_sg_connection_mock.call_count, 2)
