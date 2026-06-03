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

from tank_test.tank_test_base import ShotgunTestBase
from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.mock_appstore import MockStore, TankMockStoreDescriptor, patch_app_store

from sgtk.descriptor import Descriptor
from sgtk.descriptor import create_descriptor


class TestMockStore(ShotgunTestBase):
    """
    Tests the mocker to see if it behaves as expected.
    """

    @patch_app_store
    def test_decorated(self, mock_store):
        pass
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
                Descriptor.ENGINE,
            ),
            TankMockStoreDescriptor,
        )

    def test_non_decorated(self):
        pass
    @patch_app_store
    def test_framework_registration(self, mock_store):
        pass
