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
import base64
import pytest

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import ShotgunTestBase

from mock import patch

from tank.authentication import user, user_impl, errors
from tank_vendor.shotgun_api3 import AuthenticationFault
from tank_vendor import six

# Create a set of valid cookies, for SSO and Web related tests.
# For a Web session, we detect the presence of the shotgun_current_session_expiration cookie.
valid_web_session_metadata = base64.b64encode(
    six.ensure_binary("shotgun_current_session_expiration=1234")
)
# For a Saml session, we detect the presence of the shotgun_sso_session_expiration_u* cookie.
# But we also need to figure out what the user ID is, for which we use the csrf_token_u* suffix.
valid_sso_session_metadata = base64.b64encode(
    six.ensure_binary("csrf_token_u00=fedcba;shotgun_sso_session_expiration_u00=4321")
)


class UserTests(ShotgunTestBase):
    def _create_test_user(self):
        return user.ShotgunUser(
            user_impl.SessionUser(
                host="https://tank.shotgunstudio.com",
                login="login",
                session_token="session_token",
                http_proxy="http_proxy",
            )
        )

    def _create_script_user(self):
        return user.ShotgunUser(
            user_impl.ScriptUser(
                host="host",
                api_script="api_script",
                api_key="api_key",
                http_proxy="http_proxy",
            )
        )

    def _create_test_web_user(self):
        return user.ShotgunWebUser(
            user_impl.SessionUser(
                host="https://tank.shotgunstudio.com",
                login="login",
                session_token="session_token",
                http_proxy="http_proxy",
                session_metadata=valid_web_session_metadata,
            )
        )

    def _create_test_saml_user(self):
        return user.ShotgunSamlUser(
            user_impl.SessionUser(
                host="https://tank.shotgunstudio.com",
                login="login",
                session_token="session_token",
                http_proxy="http_proxy",
                session_metadata=valid_sso_session_metadata,
            )
        )

    def test_attributes_valid(self):
        user = self._create_test_user()
        self.assertEqual(user.host, "https://tank.shotgunstudio.com")
        self.assertEqual(user.login, "login")
        self.assertEqual(user.http_proxy, "http_proxy")

    def test_login_value(self):
        session_user = user.ShotgunUser(
            user_impl.SessionUser(
                host="https://tank.shotgunstudio.com",
                login="session_user",
                session_token="session_token",
                http_proxy="http_proxy",
            )
        )
        self.assertEqual(session_user.login, "session_user")

        script_user = self._create_script_user()
        self.assertIsNone(script_user.login)

        class CustomUser(user_impl.ShotgunUserImpl):
            def __init__(self):
                super(CustomUser, self).__init__("https://test.shotgunstudio.com", None)

            def get_login(self):
                return "custom_user"

        custom_user = user.ShotgunUser(CustomUser())

        self.assertEqual(custom_user.login, "custom_user")

    def test_serialize_deserialize(self):
        """
        Makes sure serialization and deserialization works for users
        """
        # First start with a non-Web/non-SAML user.
        su = self._create_test_user()
        self.assertNotIsInstance(su, user.ShotgunSamlUser)
        self.assertFalse("session_metadata" in su.impl.to_dict())
        su_2 = user.deserialize_user(user.serialize_user(su))
        self.assertNotIsInstance(su_2, user.ShotgunSamlUser)
        self.assertEqual(su.host, su_2.host)
        self.assertEqual(su.http_proxy, su_2.http_proxy)
        self.assertEqual(su.login, su_2.login)
        self.assertEqual(su.impl.get_session_token(), su_2.impl.get_session_token())

        # Then, with a Web user.
        su = self._create_test_web_user()
        self.assertIsInstance(su, user.ShotgunWebUser)
        self.assertTrue("session_metadata" in su.impl.to_dict())
        su_2 = user.deserialize_user(user.serialize_user(su))
        self.assertIsInstance(su_2, user.ShotgunWebUser)
        self.assertEqual(su.host, su_2.host)
        self.assertEqual(su.http_proxy, su_2.http_proxy)
        self.assertEqual(su.login, su_2.login)
        self.assertEqual(su.impl.get_session_token(), su_2.impl.get_session_token())

        # Then, with a SAML user.
        su = self._create_test_saml_user()
        self.assertIsInstance(su, user.ShotgunSamlUser)
        self.assertTrue("session_metadata" in su.impl.to_dict())
        su_2 = user.deserialize_user(user.serialize_user(su))
        self.assertIsInstance(su_2, user.ShotgunSamlUser)
        self.assertEqual(su.host, su_2.host)
        self.assertEqual(su.http_proxy, su_2.http_proxy)
        self.assertEqual(su.login, su_2.login)
        self.assertEqual(su.impl.get_session_token(), su_2.impl.get_session_token())

        su = self._create_script_user()

        su_2 = user.deserialize_user(user.serialize_user(su))
        self.assertEqual(su.host, su_2.host)
        self.assertEqual(su.http_proxy, su_2.http_proxy)
        self.assertEqual(su.login, su_2.login)
        self.assertEqual(su.impl.get_key(), su_2.impl.get_key())
        self.assertEqual(su.impl.get_script(), su_2.impl.get_script())

        # Make sure we can unserialize a user with data that is not completely understood.
        user_with_unknown_data = {
            "host": "https://test.shotgunstudio.com",
            "login": "login",
            "session_token": "token",
            "http_proxy": "127.0.0.1",
            "unexpected": "stuff",
        }

        user_impl.SessionUser.from_dict(user_with_unknown_data)

        script_user_with_unknown_data = {
            "host": "https://test.shotgunstudio.com",
            "api_script": "x123",
            "api_key": "x12333",
            "http_proxy": "127.0.0.1",
            "unexpected": "stuff",
        }
        user_impl.ScriptUser.from_dict(script_user_with_unknown_data)

    @patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    @patch("tank_vendor.shotgun_api3.Shotgun._call_rpc")
    @patch("tank.authentication.interactive_authentication.renew_session")
    def test_refresh_credentials_failure(
        self, renew_session_mock, call_rpc_mock, server_caps_mock
    ):
        """
        Makes sure we can refresh credentials correctly.

        :param renew_session_mock: Mock for the renew_session method in interactive_authentication.
        :param renew_session_mock: Mock for the _call_rpc method on the Shotgun class.
        """

        su = self._create_test_user()

        # First make sure we are failing if the session is not renewed correctly.
        call_rpc_mock.side_effect = AuthenticationFault()
        sg = su.create_sg_connection()
        with self.assertRaises(AuthenticationFault):
            sg._call_rpc()

    @patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    @patch("tank_vendor.shotgun_api3.Shotgun._call_rpc")
    @patch("tank.authentication.interactive_authentication.renew_session")
    def test_refresh_credentials_on_old_connection(
        self, renew_session_mock, call_rpc_mock, server_caps_mock
    ):
        """
        Makes sure that an existing connection with old session token can still be
        refreshed with the newer token on the user object.

        :param renew_session_mock: Mock for the renew_session method in interactive_authentication.
        :param renew_session_mock: Mock for the _call_rpc method on the Shotgun class.
        """

        su = self._create_test_user()

        # Simulate a session renewal has happened since the Shotgun connection
        # creationg
        sg = su.create_sg_connection()
        su.impl.set_session_token("session_token_2")

        # Make sure the Shotgun instance still has the old value.
        self.assertEqual(sg.config.session_token, "session_token")

        # Trigger _call_rpc to make sure sure the ShotgunWrapper copied over the session_token.
        sg._call_rpc()
        self.assertEqual(sg._user.get_session_token(), "session_token_2")

    def test_unresolvable_user(self):
        """
        Ensure the errors strings are properly formatted when we can't resolve a user's
        entity dict.
        """
        assert str(errors.UnresolvableHumanUser("jf")) == (
            "The person named 'jf' could not be resolved. Check if the "
            "permissions for the current user are hiding the field "
            "'HumanUser.login'."
        )
        assert str(errors.UnresolvableScriptUser("robot-jf")) == (
            "The script named 'robot-jf' could not be resolved. Check if the "
            "permissions for the current user are hiding the field "
            "'ApiUser.firstname'."
        )

    def test_resolving_human_user(self):
        """
        Ensure HumanUser.resolve_entity behaves properly.
        """
        self._test_resolve_entity(
            "SessionUser",
            "HumanUser",
            "login",
            "login",
            self._create_test_user,
            errors.UnresolvableHumanUser,
        )

    def test_resolving_script_user(self):
        """
        Ensure ScriptUser.resolve_entity behaves properly.
        """
        self._test_resolve_entity(
            "ScriptUser",
            "ApiUser",
            "firstname",
            "api_script",
            self._create_script_user,
            errors.UnresolvableScriptUser,
        )

    def _test_resolve_entity(
        self, class_name, entity_type, field_name, field_value, factory, error_type
    ):
        with patch(
            "tank.authentication.user_impl.%s.create_sg_connection" % class_name,
            return_value=self.mockgun,
        ):
            user = factory()
            # When the user can't be found, an error should be raised.
            with pytest.raises(error_type):
                user.resolve_entity()

            entity = self.mockgun.create(entity_type, {field_name: field_value})
            # clean up the entity dict so we can easily compare it with the resolve_entity() result.
            entity = {"type": entity["type"], "id": entity["id"]}
            # When the user exists, it should be resolved properly.
            resolved_entity = user.resolve_entity()
            assert entity == resolved_entity
