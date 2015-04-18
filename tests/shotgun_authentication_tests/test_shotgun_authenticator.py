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

from tank_vendor.shotgun_authentication import ShotgunAuthenticator, IncompleteCredentials, DefaultsManager, user


class ShotgunAuthenticatorTests(TankTestBase):

    @patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    @patch("tank_vendor.shotgun_authentication.session_cache.generate_session_token")
    def test_create_session_user(self, generate_session_token_mock, server_caps_mock):
        """
        Makes sure that create_session_user does correct input validation.
        :param generate_session_token_mock: Mocked so we can skip communicating
                                            with the Shotgun server.
        """
        generate_session_token_mock.return_value = "session_token"

        # No login should throw
        with self.assertRaises(IncompleteCredentials):
            ShotgunAuthenticator().create_session_user("", "session_token")

        # No password or session token should throw
        with self.assertRaises(IncompleteCredentials):
            ShotgunAuthenticator().create_session_user("login")

        # Passing a password should generate a session token
        user = ShotgunAuthenticator().create_session_user(
            "login", password="password", host="https://host.shotgunstudio.com"
        )
        self.assertEquals(generate_session_token_mock.call_count, 1)
        self.assertEquals(user.get_session_token(), "session_token")

        connection = user.create_sg_connection()
        self.assertEqual(connection.config.session_token, "session_token")

    @patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    def test_create_script_user(self, server_caps_mock):
        """
        Makes sure that create_script_user does correct input validation.
        """

        # No script name should throw
        with self.assertRaises(IncompleteCredentials):
            ShotgunAuthenticator().create_script_user("", "api_key")

        # No script key should throw
        with self.assertRaises(IncompleteCredentials):
            ShotgunAuthenticator().create_script_user("api_script", "")

        # With valid values it should work
        user = ShotgunAuthenticator().create_script_user(
            "api_script", "api_key", "https://host.shotgunstudio.com", None
        )
        connection = user.create_sg_connection()
        self.assertEqual(connection.config.script_name, "api_script")
        self.assertEqual(connection.config.api_key, "api_key")

    @patch("tank_vendor.shotgun_authentication.session_cache.generate_session_token")
    def test_get_default_user(self, generate_session_token_mock):
        """
        Makes sure get_default_user handles all the edge cases.
        :param generate_session_token_mock: Mocked so we can skip communicating
                                            with the Shotgun server.
        """
        generate_session_token_mock.return_value = "session_token"

        # No default user should return None if the default manager doesn't
        # provide one.
        self.assertIsNone(ShotgunAuthenticator().get_default_user())

        class ScriptDefaultManager(DefaultsManager):
            def get_user_credentials(self):
                return self.user

        dm = ScriptDefaultManager()
        # Make sure missing the api_script throws.
        dm.user = {"api_key": "api_key"}
        with self.assertRaises(IncompleteCredentials):
            ShotgunAuthenticator(dm).get_default_user()

        # Make sure missing the api_key throws.
        dm.user = {"api_script": "api_script"}
        with self.assertRaises(IncompleteCredentials):
            ShotgunAuthenticator(dm).get_default_user()

        # Make sure missing password or session_token throws.
        dm.user = {"login": "login"}
        with self.assertRaises(IncompleteCredentials):
            ShotgunAuthenticator(dm).get_default_user()

        # Make sure missing login throws.
        dm.user = {"password": "password"}
        with self.assertRaises(IncompleteCredentials):
            ShotgunAuthenticator(dm).get_default_user()

        # Make sure missing login throws.
        dm.user = {"session_token": "session_token"}
        with self.assertRaises(IncompleteCredentials):
            ShotgunAuthenticator(dm).get_default_user()

        # If we can't determine the user time, it should throw.
        dm.user = {"alien_user": "elohim"}
        with self.assertRaises(IncompleteCredentials):
            ShotgunAuthenticator(dm).get_default_user()

        # Test when the credentials are properly set up
        dm.user = {"api_script": "api_script", "api_key": "api_key"}
        self.assertIsInstance(ShotgunAuthenticator(dm).get_default_user(), user.ScriptUser)

        dm.user = {"login": "login", "session_token": "session_token"}
        self.assertIsInstance(ShotgunAuthenticator(dm).get_default_user(), user.SessionUser)

        dm.user = {"login": "login", "password": "password"}
        self.assertIsInstance(ShotgunAuthenticator(dm).get_default_user(), user.SessionUser)
