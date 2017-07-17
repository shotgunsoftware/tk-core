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

    def test_compatibility(self):

        # Utils backwards compatibility
        self.assertEqual(
            sgtk.authentication.CoreDefaultsManager,
            sgtk.util.CoreDefaultsManager
        )

        # Descriptor backwards compatibility
        self.assertEqual(
            sgtk.descriptor.InvalidAppStoreCredentialsError,
            sgtk.descriptor.TankInvalidAppStoreCredentialsError
        )
        self.assertEqual(
            sgtk.descriptor.CheckVersionConstraintsError,
            sgtk.descriptor.TankCheckVersionConstraintsError
        )

        # Core api compatibility
        self.assertEqual(
            sgtk.TankInvalidInterpreterLocationError,
            sgtk.descriptor.TankInvalidInterpreterLocationError
        )

