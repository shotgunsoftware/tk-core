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

from tank.util import login

from tank.util.core_authentication_manager import CoreAuthenticationManager
from tank_vendor.shotgun_authentication import session
from tank_vendor.shotgun_api3 import shotgun


class AuthenticationTests(TankTestBase):
    """
    Tests the session module. Note that because how caching the session information is still
    very much in flux, we will not be unit testing cache_session_info, get_login_info and
    delete_session_data for now, since they have complicated to test and would simply slow us down.
    """

    @patch("tank_vendor.shotgun_authentication.authentication.is_script_user_authenticated")
    @patch("tank_vendor.shotgun_authentication.authentication.is_human_user_authenticated")
    def setUp(
        self,
        is_human_user_authenticated_mock,
        is_script_user_authenticated_mock,
    ):
        if not CoreAuthenticationManager.is_activated():
            CoreAuthenticationManager.activate()

        # setUp in the base class tries to configure some path-cache related stuff, which invokes
        # get_current_user. We can't want a current user, so report that nothing has been authenticated.
        is_human_user_authenticated_mock.return_value = False
        is_script_user_authenticated_mock.return_value = False

        super(AuthenticationTests, self).setUp()

    @patch("tank_vendor.shotgun_authentication.session._validate_session_token")
    def test_create_from_valid_session(self, validate_session_token_mock):
        """
        When cache info is valid and _validate_session_token succeeds, it's return value
        is returned by create_sg_connection_from_authentication.
        """
        # The return value of the _validate_session_token is also the return value of
        # _create_sg_connection_from_session. Make sure we are getting it.
        validate_session_token_mock.return_value = "Success"
        self.assertEqual(session.create_sg_connection_from_session(
            {"host": "abc", "login": "login", "session_token": "session_token"}
        ), "Success")

    @patch("tank_test.mockgun.Shotgun.find_one")
    def test_authentication_failure_in_validate_session_token(self, find_one_mock):
        """
        In _validate_session_token, if find_one throws AuthenticationFault exception, we should
        fail gracefully
        """
        # find_one should throw the AuthenticationFault, which should gracefully abort connecting
        # to Shotgun
        find_one_mock.side_effect = shotgun.AuthenticationFault
        self.assertEquals(
            session._validate_session_token("https://a.com", "b", None, tank_test.mockgun.Shotgun), None
        )

    @patch("tank_test.mockgun.Shotgun.find_one")
    def test_unexpected_failure_in_validate_session_token(self, find_one_mock):
        """
        In _validate_session_token, if find_one throws anything else than AuthenticationFault, it 
        should be rethrown.
        """
        # Any other error type than AuthenticationFailed is unexpected and should be rethrown
        find_one_mock.side_effect = ValueError
        with self.assertRaises(ValueError):
            session._validate_session_token("https://a.com", "b", None, tank_test.mockgun.Shotgun)

    @patch("tank_vendor.shotgun_authentication.session._validate_session_token")
    @patch("tank_vendor.shotgun_authentication.authentication.clear_cached_credentials")
    def test_bad_credentials_should_wipe_session_data(self, validate_session_token_mock, clear_cached_credentials_mock):
        """
        When cache info is valid and _validate_session_token succeeds, it's return value
        is returned by create_sg_connection_from_authentication.
        """
        validate_session_token_mock.return_value = None
        clear_cached_credentials_mock.return_value = None
        self.assertEqual(session.create_sg_connection_from_session(
            {"host": "abc", "login": "login", "session_token": "session_token"}
        ), None)
        self.assertEqual(clear_cached_credentials_mock.call_count, 1)
