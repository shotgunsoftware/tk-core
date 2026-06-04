# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import base64

from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
)

from tank_test.tank_test_base import setUpModule  # noqa

from tank.authentication import (
    ShotgunAuthenticator,
    IncompleteCredentials,
    DefaultsManager,
    user_impl,
    user,
)

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


class CustomDefaultManager(DefaultsManager):
    def get_host(self):
        return "https://some_site.shotgunstudio.com"


class ShotgunAuthenticatorTests(ShotgunTestBase):
    @mock.patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    @mock.patch("tank.authentication.session_cache.generate_session_token")
    @mock.patch("tank.util.LocalFileStorageManager.get_global_root")
    def test_create_session_user(
        self, get_global_root, generate_session_token_mock, server_caps_mock
    ):
        pass
    @mock.patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    def test_create_script_user(self, server_caps_mock):
        pass
    @mock.patch("tank.authentication.session_cache.get_current_host", return_value=None)
    def test_no_current_host(self, _):
        pass
    @mock.patch("tank.authentication.session_cache.generate_session_token")
    def test_get_default_user(self, generate_session_token_mock):
        pass
