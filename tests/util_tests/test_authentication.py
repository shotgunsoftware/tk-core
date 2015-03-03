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
from tank_test import mockgun

from tank.util import authentication
from tank.errors import TankError

from tank_vendor.shotgun_api3 import shotgun


class SessionTests(TankTestBase):
    """
    Tests the session module. Note that because how caching the session information is still
    very much in flux, we will not be unit testing cache_session_info, get_login_info and
    delete_session_data for now, since they have complicated to test and would simply slow us down.
    """

    @patch("tank.util.authentication._shotgun_instance_factory")
    @patch("tank.util.authentication.AuthenticationManager._get_login_info")
    @patch("tank.util.shotgun.get_associated_sg_config_data")
    def run(
        self, arg0, get_associated_sg_config_data_mock, get_login_info_mock, shotgun_instance_factory_mock
    ):
        """
        Patches some api methods at a higher scope so we don't have to patch all tests individually.
        """
        # Mock the return value
        get_login_info_mock.return_value = {"login": "tk-user", "session_token": "D3ADB33F"}
        # Mock the factory method so we never create a Shotgun instance that tries to connect to the
        # site.
        shotgun_instance_factory_mock.side_effect = mockgun.Shotgun
        # Mock the return value
        get_associated_sg_config_data_mock.return_value = {"host": "https://somewhere.shotguntudio.com"}

        super(SessionTests, self).run(arg0)

    def tearDown(self):
        # Make sure an AuthenticationManager has been activated.
        authentication.AuthenticationManager.get_instance()
        # Deactivate it.
        authentication.AuthenticationManager.deactivate()

    def test_mock(self):
        """
        Make sure we are mocking get_login_info correctly"
        """
        self.assertEqual(authentication.AuthenticationManager.get_instance()._get_login_info("abc")["login"], "tk-user")
        self.assertEqual(authentication.AuthenticationManager.get_instance()._get_login_info("abc")["session_token"], "D3ADB33F")

    def test_too_many_activations(self):
        authentication.AuthenticationManager.activate()
        with self.assertRaises(TankError):
            authentication.AuthenticationManager.activate()

    @patch("tank.util.authentication._validate_session_token")
    def test_create_from_valid_session(self, validate_session_token_mock):
        """
        When cache info is valid and _validate_session_token succeeds, it's return value
        is returned by create_sg_connection_from_authentication.
        """
        # The return value of the _validate_session_token is also the return value of
        # _create_sg_connection_from_session. Make sure we are getting it.
        validate_session_token_mock.return_value = "Success"
        self.assertEqual(authentication._create_sg_connection_from_session(
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
        self.assertEquals(authentication._validate_session_token("https://a.com", "b", None), None)

    @patch("tank_test.mockgun.Shotgun.find_one")
    def test_unexpected_failure_in_validate_session_token(self, find_one_mock):
        """
        In _validate_session_token, if find_one throws AuthenticationFault exception, we should 
        fail gracefully
        """
        # Any other error type than AuthenticationFailed is unexpected and should be rethrown
        find_one_mock.side_effect = ValueError
        with self.assertRaises(ValueError):
            authentication._validate_session_token("https://a.com", "b", None)

    @patch("tank.util.authentication._validate_session_token")
    @patch("tank.util.authentication.AuthenticationManager._delete_session_data")
    def test_bad_credentials_should_wipe_session_data(self, validate_session_token_mock, delete_session_data_mock):
        """
        When cache info is valid and _validate_session_token succeeds, it's return value
        is returned by create_sg_connection_from_authentication.
        """
        validate_session_token_mock.return_value = None
        delete_session_data_mock.return_value = None
        self.assertEqual(authentication._create_sg_connection_from_session(
            {"host": "abc", "login": "login", "session_token": "session_token"}
        ), None)
        self.assertEqual(delete_session_data_mock.call_count, 1)
