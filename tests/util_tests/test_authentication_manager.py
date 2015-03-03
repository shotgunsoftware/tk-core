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

from tank.util.authentication import AuthenticationManager
from tank.util import authentication
from tank.errors import TankError

from tank_vendor.shotgun_api3 import shotgun


class SessionTests(TankTestBase):

    def tearDown(self):
        """
        """
        # Deactivate the authentication manager so other tests can use a new instance.
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
    @patch("tank.util.authentication.AuthenticationManager._get_login_info")
    def test_script_user_overrides_human_user(self, get_login_info_mock, get_associated_sg_config_data_mock):
        self._prepare_common_mocks_with_script_user(get_associated_sg_config_data_mock)
        get_login_info_mock.side_effect = Exception("Should not try to get login information.")

        cred = AuthenticationManager.get_instance().get_connection_information(force_human_user_authentication=False)
        self.assertTrue(authentication._is_script_user_authenticated(cred))
        self.assertFalse(authentication._is_human_user_authenticated(cred))

    @patch("tank.util.shotgun.get_associated_sg_config_data")
    def test_too_many_activations(self, get_associated_sg_config_data_mock):
        """
        Makes sure activating an AuthenticationManager twice will throw.
        """
        self._prepare_common_mocks_with_script_user(get_associated_sg_config_data_mock)
        authentication.AuthenticationManager.activate()
        with self.assertRaises(TankError):
            authentication.AuthenticationManager.activate()

    def test_activating_derived_class_instantiates_derived_class(self):
        """
        Makes sure that ClassDerivedFromAuthenticationManager.activate() instantiates the right
        class.
        """
        class Derived(AuthenticationManager):
            def __init__(self, payload):
                # Do not call the base class so we don't need to mock get_associated_sg_config_data.
                self.payload = payload

        # Activate our derived class.
        Derived.activate("payload")
        # Make sure the instance is the derived class.
        self.assertIsInstance(AuthenticationManager.get_instance(), Derived)
        # Make sure that the payload was
        self.assertTrue(AuthenticationManager.get_instance().payload == "payload")
