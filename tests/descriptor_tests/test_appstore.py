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

import os
import json

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
)

import sgtk
from sgtk.descriptor import Descriptor
from sgtk.descriptor.io_descriptor.base import IODescriptorBase
from sgtk.descriptor import create_descriptor

from tank import TankError
from tank.platform.environment import InstalledEnvironment


class TestAppStoreLabels(ShotgunTestBase):
    """
    Tests the app store io descriptor
    """

    def setUp(self):
        """
        Clear cached appstore connection
        """
        super().setUp()

        # work around the app store connection lookup loops to just use std mockgun instance to mock the app store
        self._get_app_store_key_from_shotgun_mock = mock.patch(
            "tank.descriptor.io_descriptor.appstore.IODescriptorAppStore._IODescriptorAppStore__create_sg_app_store_connection",
            return_value=(self.mockgun, None),
        )
        self._get_app_store_key_from_shotgun_mock.start()
        self.addCleanup(self._get_app_store_key_from_shotgun_mock.stop)

    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find_one")
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_label_support(self, find_mock, find_one_mock):
        pass
class TestAppStoreConnectivity(ShotgunTestBase):
    """
    Tests the app store io descriptor
    """

    def _create_test_descriptor(self):
        sg = self.mockgun
        root = os.path.join(self.project_root, "cache_root")

        return sgtk.descriptor.create_descriptor(
            sg,
            sgtk.descriptor.Descriptor.APP,
            {"type": "app_store", "version": "v1.1.1", "name": "tk-bundle"},
            bundle_cache_root_override=root,
        )

    def _helper_test_disabling_access_to_app_store(self, mock, expect_call):

        # Validate initial state
        self.assertEqual(mock.call_count, 0)

        # Create descriptor and check for remote access
        # which creates an app store connection
        d = self._create_test_descriptor()
        self.assertIsNotNone(d)
        d.has_remote_access()

        if expect_call:
            mock.assert_called()
        else:
            mock.assert_not_called()

        mock.reset_mock()
        self.assertEqual(mock.call_count, 0)

    @mock.patch("tank_vendor.shotgun_api3.Shotgun")
    @mock.patch("urllib.request.urlopen")
    def test_disabling_access_to_app_store(self, urlopen_mock, shotgun_mock):
        pass
class TestAppStorePythonVersionCompatibility(ShotgunTestBase):
    """
    Tests the minimum_python_version compatibility checking in app store descriptors
    """

    def setUp(self):
        """
        Clear cached appstore connection and setup mocks
        """
        super().setUp()

        # Mock the app store connection
        self._get_app_store_key_from_shotgun_mock = mock.patch(
            "tank.descriptor.io_descriptor.appstore.IODescriptorAppStore._IODescriptorAppStore__create_sg_app_store_connection",
            return_value=(self.mockgun, None),
        )
        self._get_app_store_key_from_shotgun_mock.start()
        self.addCleanup(self._get_app_store_key_from_shotgun_mock.stop)

    def _create_test_descriptor(self):
        """Helper to create a test descriptor"""
        return create_descriptor(
            None,
            Descriptor.APP,
            {"name": "tk-framework-testapp", "version": "v1.0.0", "type": "app_store"},
        )

    @mock.patch("sys.version_info", new=(3, 9, 0))
    def test_check_minimum_python_version_blocks_incompatible(self):
        pass
    @mock.patch("sys.version_info", new=(3, 11, 0))
    def test_check_minimum_python_version_allows_compatible(self):
        pass
    def test_check_minimum_python_version_handles_invalid_types(self):
        pass
    @mock.patch("sys.version_info", new=(3, 7, 0))
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find_one")
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    @mock.patch(
        "tank.descriptor.io_descriptor.appstore.IODescriptorAppStore.exists_local"
    )
    @mock.patch(
        "tank.descriptor.io_descriptor.appstore.IODescriptorAppStore.download_local"
    )
    @mock.patch(
        "tank.descriptor.io_descriptor.appstore.IODescriptorAppStore.get_manifest"
    )
    @mock.patch(
        "tank.descriptor.io_descriptor.appstore.IODescriptorAppStore._find_compatible_cached_version"
    )
    def test_python_37_uses_cached_compatible_version(
        self,
        mock_find_cached,
        mock_get_manifest,
        mock_download,
        mock_exists,
        find_mock,
        find_one_mock,
    ):
        pass
    @mock.patch("sys.version_info", new=(3, 10, 0))
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find_one")
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    @mock.patch(
        "tank.descriptor.io_descriptor.appstore.IODescriptorAppStore.exists_local"
    )
    @mock.patch(
        "tank.descriptor.io_descriptor.appstore.IODescriptorAppStore.download_local"
    )
    @mock.patch(
        "tank.descriptor.io_descriptor.appstore.IODescriptorAppStore.get_manifest"
    )
    @mock.patch(
        "tank.descriptor.io_descriptor.appstore.IODescriptorAppStore._find_compatible_cached_version"
    )
    def test_python_310_selects_version_requiring_39(
        self,
        mock_find_cached,
        mock_get_manifest,
        mock_download,
        mock_exists,
        find_mock,
        find_one_mock,
    ):
        pass
