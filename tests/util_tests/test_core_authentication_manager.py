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

from tank_vendor.shotgun_authentication.session_cache import AuthenticationManager, ActivationError
from tank.util.core_session_cache import CoreAuthenticationManager
from tank_vendor.shotgun_authentication import authentication


class AuthenticationManagerTests(TankTestBase):

    def setUp(self):
        """
        Sets up the unit test. If there is an activate authentication manager, it deactivates it.
        """
        super(AuthenticationManagerTests, self).setUp()
        # Base class caused an activation of the AuthenticationManager, so deactivate it.
        if AuthenticationManager.is_activated():
            AuthenticationManager.deactivate()

    def _prepare_common_mocks_with_script_user(self, get_associated_sg_config_data_mock):
        """
        Prepares common mocks to be used in a test involving script users.
        """
        # Makes sure the config file returns a script user.
        get_associated_sg_config_data_mock.return_value = {
            "api_key": "1234567890",
            "api_script": "Toolkit",
            "host": "https://somewhere.shotguntudio.com"
        }

    @patch("tank.util.shotgun.get_associated_sg_config_data")
    @patch("tank_vendor.shotgun_authentication.session_cache.AuthenticationManager.get_session_data")
    def test_script_user_overrides_human_user(self, get_session_data_mock, get_associated_sg_config_data_mock):
        self._prepare_common_mocks_with_script_user(get_associated_sg_config_data_mock)
        get_session_data_mock.side_effect = Exception("Should not try to get login information.")
        CoreAuthenticationManager.activate()
        cred = AuthenticationManager.get_instance().get_connection_information()
        self.assertTrue(authentication.is_script_user_authenticated(cred))
        self.assertFalse(authentication.is_human_user_authenticated(cred))
