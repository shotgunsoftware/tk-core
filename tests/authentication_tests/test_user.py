# -*- coding: utf-8 -*-

# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import base64
import pytest

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
)

from tank.authentication import user, user_impl, errors
from tank_vendor.shotgun_api3 import AuthenticationFault

# Create a set of valid cookies, for SSO and Web related tests.
# For a Web session, we detect the presence of the shotgun_current_session_expiration cookie.
valid_web_session_metadata = base64.b64encode(
    b"shotgun_current_session_expiration=1234"
)
# For a Saml session, we detect the presence of the shotgun_sso_session_expiration_u* cookie.
# But we also need to figure out what the user ID is, for which we use the csrf_token_u* suffix.
valid_sso_session_metadata = base64.b64encode(
    b"csrf_token_u00=fedcba;shotgun_sso_session_expiration_u00=4321"
)


class UserTests(ShotgunTestBase):
    def _create_test_user(self, login="login"):
        return user.ShotgunUser(
            user_impl.SessionUser(
                host="https://tank.shotgunstudio.com",
                login=login,
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

    def _create_test_web_user(self, login="login"):
        return user.ShotgunWebUser(
            user_impl.SessionUser(
                host="https://tank.shotgunstudio.com",
                login=login,
                session_token="session_token",
                http_proxy="http_proxy",
                session_metadata=valid_web_session_metadata,
            )
        )

    def _create_test_saml_user(self, login="login"):
        return user.ShotgunSamlUser(
            user_impl.SessionUser(
                host="https://tank.shotgunstudio.com",
                login=login,
                session_token="session_token",
                http_proxy="http_proxy",
                session_metadata=valid_sso_session_metadata,
            )
        )

    def test_attributes_valid(self):
        pass
    def test_login_value(self):
        pass
    def test_serialize_deserialize(self):
        pass
    @mock.patch(
        "tank_vendor.shotgun_api3.Shotgun._call_rpc",
        side_effect=ConnectionRefusedError(),
    )
    def test_are_credentials_expired(
        self,
        call_rpc_mock,
    ):
        pass
    @mock.patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    @mock.patch("tank_vendor.shotgun_api3.Shotgun._call_rpc")
    @mock.patch("tank.authentication.interactive_authentication.renew_session")
    def test_refresh_credentials_failure(
        self, renew_session_mock, call_rpc_mock, server_caps_mock
    ):
        pass
    @mock.patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    @mock.patch("tank_vendor.shotgun_api3.Shotgun._call_rpc")
    @mock.patch("tank.authentication.interactive_authentication.renew_session")
    def test_refresh_credentials_on_old_connection(
        self, renew_session_mock, call_rpc_mock, server_caps_mock
    ):
        pass
    def test_unresolvable_user(self):
        pass
    def test_resolving_human_user(self):
        pass
    def test_resolving_script_user(self):
        pass
    def _test_resolve_entity(
        self, class_name, entity_type, field_name, field_value, factory, error_type
    ):
        with mock.patch(
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
