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
        pass
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
        pass
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
        pass
    ):
        """
        End-to-end test: Python 3.7 uses compatible cached version (v1.0.0) instead of
        incompatible latest (v2.0.0) when calling find_latest_version().

        This test demonstrates that when the latest version is incompatible, the system searches
        the cache for a compatible version and returns it if found.
        """

        def find_one_mock_impl(*args, **kwargs):
            return {
                "type": "CustomNonProjectEntity13",
                "id": 1234,
                "sg_system_name": "tk-multi-testapp",
                "sg_status_list": "prod",
                "sg_deprecation_message": None,
            }

        def find_mock_impl(*args, **kwargs):
            # Return only v2.0.0 - the latest version from App Store
            # The Python version requirement is read from the manifest via get_manifest()
            return [
                {
                    "type": "CustomNonProjectEntity09",
                    "id": 2,
                    "code": "v2.0.0",
                    "tags": [],
                    "sg_status_list": "prod",
                    "description": "Version requiring Python 3.9",
                    "sg_detailed_release_notes": "Requires Python 3.9+",
                    "sg_documentation": "dummy",
                    "sg_payload": {},
                },
            ]

        # Setup mocks
        find_mock.side_effect = find_mock_impl
        find_one_mock.side_effect = find_one_mock_impl

        # Mock that v2.0.0 exists locally (to read its manifest)
        mock_exists.return_value = True
        # No need to download
        mock_download.return_value = None
        # Mock manifest showing v2.0.0 requires Python 3.9
        mock_get_manifest.return_value = {"minimum_python_version": "3.9"}

        # Mock _find_compatible_cached_version to return v1.0.0 descriptor
        cached_desc = self._create_test_descriptor()._io_descriptor
        mock_find_cached.return_value = cached_desc

        # Create descriptor
        desc = self._create_test_descriptor()

        # With Python 3.7, when latest (v2.0.0) is incompatible,
        # the system finds and returns v1.0.0 from cache
        latest_desc = desc.find_latest_version()

        # Should return v1.0.0 (cached compatible) instead of v2.0.0 (incompatible latest)
        self.assertEqual(latest_desc.get_version(), "v1.0.0")
        # Verify cache search was called
        mock_find_cached.assert_called_once()

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
        pass
    ):
        """
        End-to-end test: Python 3.11 DOES select a component version requiring Python 3.9
        when calling find_latest_version(). This demonstrates the positive case where the
        current Python version meets the minimum requirement.
        """

        def find_one_mock_impl(*args, **kwargs):
            return {
                "type": "CustomNonProjectEntity13",
                "id": 1234,
                "sg_system_name": "tk-multi-testapp",
                "sg_status_list": "prod",
                "sg_deprecation_message": None,
            }

        def find_mock_impl(*args, **kwargs):
            # Return only v2.0.0 - simulating latest version from App Store
            # The Python version requirement is read from the manifest via get_manifest()
            return [
                {
                    "type": "CustomNonProjectEntity09",
                    "id": 2,
                    "code": "v2.0.0",
                    "tags": [],
                    "sg_status_list": "prod",
                    "description": "Version requiring Python 3.9",
                    "sg_detailed_release_notes": "Requires Python 3.9+",
                    "sg_documentation": "dummy",
                    "sg_payload": {},
                },
            ]

        find_mock.side_effect = find_mock_impl
        find_one_mock.side_effect = find_one_mock_impl

        # Mock that v2.0.0 exists locally (to read its manifest)
        mock_exists.return_value = True
        # No need to download
        mock_download.return_value = None
        # Mock manifest showing v2.0.0 requires Python 3.9
        mock_get_manifest.return_value = {"minimum_python_version": "3.9"}
        # Mock cache search returns None - no compatible version in cache
        mock_find_cached.return_value = None

        # Create descriptor
        desc = self._create_test_descriptor()

        # With Python 3.11, find_latest_version() should successfully return v2.0.0
        # because Python 3.11 >= Python 3.9 (minimum requirement)
        latest_desc = desc.find_latest_version()

        # Should select v2.0.0 since Python 3.11 meets the minimum requirement of 3.9
        self.assertEqual(latest_desc.get_version(), "v2.0.0")
        # Verify cache search was NOT called because Python 3.11 is compatible
        mock_find_cached.assert_not_called()
