# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Unit tests tank updates.
"""

from __future__ import with_statement

import os
import re
import logging
import functools
import tempfile

import mock

from tank_test.tank_test_base import TankTestBase, setUpModule
from tank_test.mock_appstore import MockStore, TankMockStoreDescriptor, patch_app_store

import sgtk
from sgtk.descriptor import Descriptor
from sgtk.descriptor.io_descriptor.base import IODescriptorBase
from sgtk.descriptor.descriptor import create_descriptor

from tank import TankError
from tank.platform.environment import InstalledEnvironment
from distutils.version import LooseVersion



class TestMockStore(TankTestBase):
    """
    Tests the mocker to see if it behaves as expected.
    """

    @patch_app_store
    def test_decorated(self, mock_store):
        """
        Makes sure everything is patched in correctly.
        """
        self._test_patched(mock_store)

    def _test_patched(self, mock_store):
        """
        Tests that the mock_store parameter is the MockStore and that
        the TankAppStoreDescriptor class has been properly patched.
        """
        # Make sure this is the mock store.
        self.assertIsInstance(mock_store, MockStore)
        # Register an engine with it.
        mock_store.add_engine("tk-test", "v1.2.3")

        from tank.descriptor.io_descriptor.appstore import IODescriptorAppStore

        # Make sure the created object is actually an instance of the mocked descriptor class.
        self.assertIsInstance(
            IODescriptorAppStore(
                {"name": "tk-test", "type": "app_store", "version": "v1.2.3"},
                None,
                Descriptor.ENGINE
            ), TankMockStoreDescriptor
        )

    def test_non_decorated(self):
        """
        Tests the non decorated usage of the patch_app_store method.
        """
        patcher = patch_app_store()

        from tank.descriptor.io_descriptor.appstore import IODescriptorAppStore

        self.assertNotEqual(TankMockStoreDescriptor, IODescriptorAppStore)

        # Once we use the patch, everything should be mocked.
        with patcher as mock_store:
            self._test_patched(mock_store)

        # Now the patch should be unaplied and nothing should be mocked anymore.
        self.assertNotEqual(TankMockStoreDescriptor, IODescriptorAppStore)

    @patch_app_store
    def test_framework_registration(self, mock_store):
        """
        Makes sure the framework is registered correctly.
        """
        # Version this is a dependency.
        dependency = mock_store.add_framework("tk-framework-dependency", "v1.0.0")
        self.assertEqual(dependency.get_major_dependency_descriptor(), {
            "version": "v1.x.x",
            "name": "tk-framework-dependency",
            "type": "app_store"
        })
        # This is V1 of a framework that has no depdendencies.
        mock_store.add_framework("tk-framework-main", "v1.0.0")
        # This is V2 of a framework that now has a depdendency
        mock_store.add_framework("tk-framework-main", "v2.0.0").required_frameworks = [
            dependency.get_major_dependency_descriptor()
        ]

        # Makes sure we respect the interface of the TankAppStoreDescriptor

        desc = create_descriptor(
            None,
            Descriptor.FRAMEWORK,
            {"name": "tk-framework-main", "version": "v2.0.0", "type": "app_store"}
        )

        self.assertEqual(
            desc.required_frameworks,
            [{"type": "app_store", "name": "tk-framework-dependency", "version": "v1.x.x"}]
        )

        desc = create_descriptor(
            None,
            Descriptor.FRAMEWORK,
            {"name": "tk-framework-main", "version": "v1.0.0", "type": "app_store"}
        )

        self.assertEqual(desc.required_frameworks, [])


