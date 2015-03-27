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


class AuthenticationManagerTests(TankTestBase):

    def setUp(self):
        """
        Sets up the unit test. If there is an activate authentication manager, it deactivates it.
        """
        super(AuthenticationManagerTests, self).setUp()
        # Make sure there is no activated managers. Each test will activate it.
        if AuthenticationManager.is_activated():
            AuthenticationManager.deactivate()

    def test_too_many_activations(self):
        """
        Makes sure activating an AuthenticationManager twice will throw.
        """
        AuthenticationManager.activate()
        with self.assertRaises(ActivationError):
            AuthenticationManager.activate()

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
