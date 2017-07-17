# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from unittest2 import TestCase

import sgtk


class BackwardsCompatibilityTests(TestCase):

    def test_class_availability(self):
        """
        Ensures the API is backwards compatible.
        """

        # Each test should be interpreter as
        #
        # self.assertEqual(new_location, old_location)

        # Utils backwards compatibility
        self.assertEqual(
            sgtk.authentication.CoreDefaultsManager,
            sgtk.util.CoreDefaultsManager
        )

        # Descriptor backwards compatibility
        self.assertEqual(
            sgtk.descriptor.TankInvalidAppStoreCredentialsError,
            sgtk.descriptor.InvalidAppStoreCredentialsError
        )
        self.assertEqual(
            sgtk.descriptor.TankCheckVersionConstraintsError,
            sgtk.descriptor.CheckVersionConstraintsError
        )

        # Core api compatibility
        self.assertEqual(
            sgtk.descriptor.TankInvalidInterpreterLocationError,
            sgtk.TankInvalidInterpreterLocationError
        )

        self.assertEqual(
            sgtk.platform.TankEngineInitError,
            sgtk.TankEngineInitError
        )
