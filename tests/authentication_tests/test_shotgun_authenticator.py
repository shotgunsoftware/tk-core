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
import os
import base64

from tank_test.tank_test_base import ShotgunTestBase
from tank_test.tank_test_base import setUpModule # noqa

from tank.authentication import ShotgunAuthenticator, IncompleteCredentials, DefaultsManager, user_impl, user

# Create a set of valid cookies, for SSO and Web related tests.
# For a Web session, we detect the presence of the shotgun_current_session_expiration cookie.
valid_web_session_metadata = base64.b64encode('shotgun_current_session_expiration=1234')
# For a Saml session, we detect the presence of the shotgun_sso_session_expiration_u* cookie.
# But we also need to figure out what the user ID is, for which we use the csrf_token_u* suffix.
valid_sso_session_metadata = base64.b64encode('csrf_token_u00=fedcba;shotgun_sso_session_expiration_u00=4321')


class CustomDefaultManager(DefaultsManager):
    def get_host(self):
        return "https://some_site.shotgunstudio.com"


class ShotgunAuthenticatorTests(ShotgunTestBase):

    @patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    @patch("tank.authentication.session_cache.generate_session_token")
    @patch("tank.util.LocalFileStorageManager.get_global_root")
    def test_create_session_user(self, get_global_root, generate_session_token_mock, server_caps_mock):
        """
        Makes sure that create_session_user does correct input validation.
        :param generate_session_token_mock: Mocked so we can skip communicating
                                            with the Shotgun server.
        """
        generate_session_token_mock.return_value = "session_token"
        get_global_root.return_value = os.path.join(self.tank_temp, "session_cache")

        # No login should throw
        with self.assertRaises(IncompleteCredentials):
            ShotgunAuthenticator(CustomDefaultManager()).create_session_user("", "session_token")

        # No password or session token should throw
        with self.assertRaises(IncompleteCredentials):
            ShotgunAuthenticator(CustomDefaultManager()).create_session_user("login")

        # Passing a password should generate a session token
        session_user = ShotgunAuthenticator(CustomDefaultManager()).create_session_user(
            "login", password="password", host="https://host.shotgunstudio.com"
        )
        self.assertIsInstance(session_user, user.ShotgunUser)
        self.assertNotIsInstance(session_user, user.ShotgunWebUser)
        self.assertNotIsInstance(session_user, user.ShotgunSamlUser)
        self.assertEqual(generate_session_token_mock.call_count, 1)
        self.assertEqual(session_user.impl.get_session_token(), "session_token")

        connection = session_user.create_sg_connection()
        self.assertEqual(connection.config.session_token, "session_token")

        # Passing invalid session_metadata will result in a regular ShotgunUser
        session_user = ShotgunAuthenticator(CustomDefaultManager())._create_session_user(
            "login", password="password", host="https://host.shotgunstudio.com",
            session_metadata="invalid session_metadata"
        )
        self.assertIsInstance(session_user, user.ShotgunUser)
        self.assertNotIsInstance(session_user, user.ShotgunWebUser)
        self.assertNotIsInstance(session_user, user.ShotgunSamlUser)
        self.assertEqual(generate_session_token_mock.call_count, 2)
        self.assertEqual(session_user.impl.get_session_token(), "session_token")

        connection = session_user.create_sg_connection()
        self.assertEqual(connection.config.session_token, "session_token")

        # Passing valid session_metadata will result in a ShotgunWebUser
        session_user = ShotgunAuthenticator(CustomDefaultManager())._create_session_user(
            "login", password="password", host="https://host.shotgunstudio.com",
            session_metadata=valid_web_session_metadata
        )
        self.assertIsInstance(session_user, user.ShotgunWebUser)
        self.assertNotIsInstance(session_user, user.ShotgunSamlUser)
        self.assertEqual(generate_session_token_mock.call_count, 3)
        self.assertEqual(session_user.impl.get_session_token(), "session_token")

        connection = session_user.create_sg_connection()
        self.assertEqual(connection.config.session_token, "session_token")

        # Passing valid session_metadata will result in a ShotgunSamlUser
        session_user = ShotgunAuthenticator(CustomDefaultManager())._create_session_user(
            "login", password="password", host="https://host.shotgunstudio.com",
            session_metadata=valid_sso_session_metadata
        )
        self.assertIsInstance(session_user, user.ShotgunSamlUser)
        self.assertEqual(generate_session_token_mock.call_count, 4)
        self.assertEqual(session_user.impl.get_session_token(), "session_token")

        connection = session_user.create_sg_connection()
        self.assertEqual(connection.config.session_token, "session_token")

    @patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    def test_create_script_user(self, server_caps_mock):
        """
        Makes sure that create_script_user does correct input validation.
        """
        # No script name should throw
        with self.assertRaises(IncompleteCredentials):
            ShotgunAuthenticator(CustomDefaultManager()).create_script_user("", "api_key")

        # No script key should throw
        with self.assertRaises(IncompleteCredentials):
            ShotgunAuthenticator(CustomDefaultManager()).create_script_user("api_script", "")

        # With valid values it should work
        user = ShotgunAuthenticator(CustomDefaultManager()).create_script_user(
            "api_script", "api_key", "https://host.shotgunstudio.com", None
        )
        connection = user.create_sg_connection()
        self.assertEqual(connection.config.script_name, "api_script")
        self.assertEqual(connection.config.api_key, "api_key")

    @patch("tank.authentication.session_cache.get_current_host", return_value=None)
    def test_no_current_host(self, _):
        """
        Makes sure the login is None when there is no host.
        """
        self.assertIsNone(DefaultsManager().get_login())

    @patch("tank.authentication.session_cache.generate_session_token")
    def test_get_default_user(self, generate_session_token_mock):
        """
        Makes sure get_default_user handles all the edge cases.
        :param generate_session_token_mock: Mocked so we can skip communicating
                                            with the Shotgun server.
        """
        generate_session_token_mock.return_value = "session_token"

        class TestWithUserDefaultManager(CustomDefaultManager):
            def get_host(self):
                return "https://unique_host.shotgunstudio.com"

            def get_user_credentials(self):
                return self.user

        dm = TestWithUserDefaultManager()

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
        self.assertIsInstance(ShotgunAuthenticator(dm).get_default_user().impl, user_impl.ScriptUser)

        dm.user = {"login": "login", "session_token": "session_token"}
        default_user = ShotgunAuthenticator(dm).get_default_user()
        self.assertIsInstance(default_user, user.ShotgunUser)
        self.assertNotIsInstance(default_user, user.ShotgunWebUser)
        self.assertNotIsInstance(default_user, user.ShotgunSamlUser)
        self.assertIsInstance(default_user.impl, user_impl.SessionUser)

        dm.user = {"login": "login", "password": "password"}
        default_user = ShotgunAuthenticator(dm).get_default_user()
        self.assertIsInstance(default_user, user.ShotgunUser)
        self.assertNotIsInstance(default_user, user.ShotgunWebUser)
        self.assertNotIsInstance(default_user, user.ShotgunSamlUser)
        self.assertIsInstance(default_user.impl, user_impl.SessionUser)

        dm.user = {"login": "login", "password": "password", "session_metadata": "invalid session_metadata"}
        default_user = ShotgunAuthenticator(dm).get_default_user()
        self.assertIsInstance(default_user, user.ShotgunUser)
        self.assertNotIsInstance(default_user, user.ShotgunWebUser)
        self.assertNotIsInstance(default_user, user.ShotgunSamlUser)
        self.assertIsInstance(default_user.impl, user_impl.SessionUser)

        dm.user = {"login": "login", "password": "password", "session_metadata": valid_web_session_metadata}
        default_user = ShotgunAuthenticator(dm).get_default_user()
        self.assertIsInstance(default_user, user.ShotgunWebUser)
        self.assertNotIsInstance(default_user, user.ShotgunSamlUser)
        self.assertIsInstance(default_user.impl, user_impl.SessionUser)

        dm.user = {"login": "login", "password": "password", "session_metadata": valid_sso_session_metadata}
        default_user = ShotgunAuthenticator(dm).get_default_user()
        self.assertIsInstance(default_user, user.ShotgunSamlUser)
        self.assertIsInstance(default_user.impl, user_impl.SessionUser)
