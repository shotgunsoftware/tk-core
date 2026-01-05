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
        """
        Tests the label syntax and that it restricts versions correctly
        """

        def find_one_mock_impl(*args, **kwargs):
            """
            The app store implementation will call this once to resolve the main
            app as part of retrieving latest.
            Expected form:

            args: (
                'CustomNonProjectEntity13',
                [['sg_system_name', 'is', 'tk-framework-main']],
                ['id', 'sg_system_name', 'sg_status_list', 'sg_deprecation_message']
                )
            kwargs: {}
            """
            # ensure that input is what we expected
            self.assertEqual(kwargs, {})
            self.assertEqual(
                args,
                (
                    "CustomNonProjectEntity13",
                    [["sg_system_name", "is", "tk-framework-main"]],
                    [
                        "id",
                        "sg_system_name",
                        "sg_status_list",
                        "sg_deprecation_message",
                    ],
                ),
            )

            return {
                "type": "CustomNonProjectEntity13",
                "id": 1234,
                "sg_system_name": "tk-framework-main",
                "sg_status_list": "prod",
                "sg_deprecation_message": None,
            }

        def find_mock_impl(*args, **kwargs):
            """
            The find call to get app store versions will arrive here as a consequence
            of the find_latest_version call.
            Expected form:

            args: ('CustomNonProjectEntity09',)
            kwargs: {
                'fields': [
                    'id', 'code', 'sg_status_list', 'description', 'tags', 'sg_detailed_release_notes',
                    'sg_documentation', 'sg_payload'
                ],
                'limit': 1,
                'order': [{'direction': 'desc', 'field_name': 'created_at'}],
                'filters': [['sg_status_list', 'is_not', 'rev'], ['sg_status_list', 'is_not', 'bad'],
                            ['sg_tank_framework', 'is', {'sg_status_list': 'prod', 'type': 'CustomNonProjectEntity13', 'id': 1234,
               'sg_system_name': 'tk-framework-main',
               'sg_deprecation_message': None}]]
            }
            """
            self.assertEqual(args, ("CustomNonProjectEntity09",))

            # app store is trying to be smart about bandwidth depending on queries, so limit may vary.
            kwargs["limit"] = None

            self.assertEqual(
                kwargs,
                {
                    "fields": [
                        "id",
                        "code",
                        "sg_status_list",
                        "description",
                        "tags",
                        "sg_detailed_release_notes",
                        "sg_documentation",
                        "sg_payload",
                    ],
                    "limit": None,
                    "order": [{"direction": "desc", "field_name": "created_at"}],
                    "filters": [
                        ["sg_status_list", "is_not", "rev"],
                        ["sg_status_list", "is_not", "bad"],
                        [
                            "sg_tank_framework",
                            "is",
                            {
                                "sg_status_list": "prod",
                                "type": "CustomNonProjectEntity13",
                                "id": 1234,
                                "sg_system_name": "tk-framework-main",
                                "sg_deprecation_message": None,
                            },
                        ],
                    ],
                },
            )

            return_data = []

            return_data.append(
                {
                    "type": "CustomNonProjectEntity09",
                    "id": 1,
                    "code": "v1.0.1",
                    "tags": [
                        {"id": 1, "name": "2017.*", "type": "Tag"},
                        {"id": 2, "name": "2016.*", "type": "Tag"},
                    ],
                    "sg_detailed_release_notes": "Test 1",
                    "sg_status_list": "prod",
                    "description": "dummy",
                    "sg_detailed_release_notes": "dummy",
                    "sg_documentation": "dummy",
                    "sg_payload": {},
                }
            )

            return_data.append(
                {
                    "type": "CustomNonProjectEntity09",
                    "id": 2,
                    "code": "v2.0.1",
                    "tags": [{"id": 1, "name": "2017.*", "type": "Tag"}],
                    "sg_detailed_release_notes": "Test 2",
                    "sg_status_list": "prod",
                    "description": "dummy",
                    "sg_detailed_release_notes": "dummy",
                    "sg_documentation": "dummy",
                    "sg_payload": {},
                }
            )

            return_data.append(
                {
                    "type": "CustomNonProjectEntity09",
                    "id": 3,
                    "code": "v3.0.1",
                    "tags": [{"id": 3, "name": "2018.*", "type": "Tag"}],
                    "sg_detailed_release_notes": "Test 3",
                    "sg_status_list": "prod",
                    "description": "dummy",
                    "sg_detailed_release_notes": "dummy",
                    "sg_documentation": "dummy",
                    "sg_payload": {},
                }
            )

            # return it in desc/reverse order, e.g. higher versions last, as requested by the API call
            return return_data[::-1]

        find_mock.side_effect = find_mock_impl
        find_one_mock.side_effect = find_one_mock_impl

        # no label
        desc = create_descriptor(
            None,
            Descriptor.FRAMEWORK,
            {"name": "tk-framework-main", "version": "v1.0.0", "type": "app_store"},
        )
        self.assertEqual(
            desc.get_uri(),
            "sgtk:descriptor:app_store?name=tk-framework-main&version=v1.0.0",
        )
        desc2 = desc.find_latest_version()
        self.assertEqual(
            desc2.get_uri(),
            "sgtk:descriptor:app_store?name=tk-framework-main&version=v3.0.1",
        )

        # i am version 2016.3.45 so i am only getting 1.0.1
        desc = create_descriptor(
            None,
            Descriptor.FRAMEWORK,
            {
                "name": "tk-framework-main",
                "version": "v1.0.0",
                "type": "app_store",
                "label": "2016.3.45",
            },
        )
        self.assertEqual(
            desc.get_uri(),
            "sgtk:descriptor:app_store?label=2016.3.45&name=tk-framework-main&version=v1.0.0",
        )
        desc2 = desc.find_latest_version()
        self.assertEqual(
            desc2.get_uri(),
            "sgtk:descriptor:app_store?label=2016.3.45&name=tk-framework-main&version=v1.0.1",
        )

        # i am version 2017.3.45 so i am getting 2.0.1
        desc = create_descriptor(
            None,
            Descriptor.FRAMEWORK,
            {
                "name": "tk-framework-main",
                "version": "v1.0.0",
                "type": "app_store",
                "label": "2017.3.45",
            },
        )
        self.assertEqual(
            desc.get_uri(),
            "sgtk:descriptor:app_store?label=2017.3.45&name=tk-framework-main&version=v1.0.0",
        )
        desc2 = desc.find_latest_version()
        self.assertEqual(
            desc2.get_uri(),
            "sgtk:descriptor:app_store?label=2017.3.45&name=tk-framework-main&version=v2.0.1",
        )

        # i am version 2018.3.45 so i am getting 3.0.1
        desc = create_descriptor(
            None,
            Descriptor.FRAMEWORK,
            {
                "name": "tk-framework-main",
                "version": "v1.0.0",
                "type": "app_store",
                "label": "2018.3.45",
            },
        )
        self.assertEqual(
            desc.get_uri(),
            "sgtk:descriptor:app_store?label=2018.3.45&name=tk-framework-main&version=v1.0.0",
        )
        desc2 = desc.find_latest_version()
        self.assertEqual(
            desc2.get_uri(),
            "sgtk:descriptor:app_store?label=2018.3.45&name=tk-framework-main&version=v3.0.1",
        )


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
        """
        Tests that we can prevent connection to the app store based on usage
        of the `SHOTGUN_DISABLE_APPSTORE_ACCESS` environment variable.
        """

        def urlopen_mock_impl(*args, **kwargs):
            """
            Necessary mock so we can pass beyond:
            - `
                - `appstore.IODescriptorAppStore.__create_sg_app_store_connection()`
                    - appstore.IODescriptorAppStore.__get_app_store_key_from_shotgun()`

            Otherwise the code would always cause an exception that is caught by the
            the `appstore.IODescriptorAppStore.has_remote_access()` except statement
            which causes the method to return False all of the time which then
            prevents execution of the code of interest.
            """

            class MockResponse:
                """
                Custom mocked response to allow successful execution of the
                `appstore.IODescriptorAppStore.__get_app_store_key_from_shotgun()` method.
                """

                def __init__(self, json_data, status_code):
                    self.json_data = json.JSONEncoder().encode(json_data)
                    self.status_code = status_code

                def read(self):
                    return str(self.json_data)

            uri = args[0]
            if uri == "http://unit_test_mock_sg/api3/sgtk_install_script":
                return MockResponse(
                    {
                        "script_name": "bogus_script_name",
                        "script_key": "bogus_script_key",
                    },
                    200,
                )

            return MockResponse(None, 404)

        def shotgun_mock_impl(*args, **kwargs):
            """
            Mocking up shotgun_api3.Shotgun() constructor.
            We're not really interested in mocking what it does as much as
            verifying whether or not an instance is created from calling the
            `appstore.IODescriptorAppStore.has_remote_access()` method.
            """
            pass

        shotgun_mock.side_effect = shotgun_mock_impl
        urlopen_mock.side_effect = urlopen_mock_impl

        # NOTE: We're not using the tank.descriptor.constants.DISABLE_APPSTORE_ACCESS_ENV_VAR
        # constant so we can independently tests that the name of the used environment
        # variable did not change.
        env_var_name = "SHOTGUN_DISABLE_APPSTORE_ACCESS"

        # Test without the environment variable being present
        # First we delete it from environ
        if env_var_name in os.environ:
            del os.environ[env_var_name]
        self._helper_test_disabling_access_to_app_store(shotgun_mock, True)

        # Test present inactive
        os.environ[env_var_name] = "0"
        self._helper_test_disabling_access_to_app_store(shotgun_mock, True)

        # Test present active
        os.environ[env_var_name] = "1"
        self._helper_test_disabling_access_to_app_store(shotgun_mock, False)

        # Test present inactive (again)
        os.environ[env_var_name] = "0"
        self._helper_test_disabling_access_to_app_store(shotgun_mock, True)


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
        """
        Test that _check_minimum_python_version correctly identifies incompatible versions
        """
        desc = self._create_test_descriptor()
        io_desc = desc._io_descriptor

        # Manifest requiring Python 3.10 should be incompatible with Python 3.9
        self.assertFalse(
            io_desc._check_minimum_python_version({"minimum_python_version": "3.10"})
        )

        # Manifest requiring Python 3.7 should be compatible with Python 3.9
        self.assertTrue(
            io_desc._check_minimum_python_version({"minimum_python_version": "3.7"})
        )

        # Manifest without requirement should be compatible
        self.assertTrue(io_desc._check_minimum_python_version({}))

    @mock.patch("sys.version_info", new=(3, 11, 0))
    def test_check_minimum_python_version_allows_compatible(self):
        """
        Test that _check_minimum_python_version correctly identifies compatible versions
        """
        desc = self._create_test_descriptor()
        io_desc = desc._io_descriptor

        # Manifest requiring Python 3.10 should be compatible with Python 3.11
        self.assertTrue(
            io_desc._check_minimum_python_version({"minimum_python_version": "3.10"})
        )

        # Manifest requiring Python 3.11 should be compatible with Python 3.11
        self.assertTrue(
            io_desc._check_minimum_python_version({"minimum_python_version": "3.11"})
        )

        # Manifest requiring Python 3.12 should NOT be compatible with Python 3.11
        self.assertFalse(
            io_desc._check_minimum_python_version({"minimum_python_version": "3.12"})
        )

    def test_check_minimum_python_version_handles_invalid_types(self):
        """
        Test that _check_minimum_python_version handles invalid minimum_python_version types gracefully
        """
        desc = self._create_test_descriptor()
        io_desc = desc._io_descriptor

        # Non-string types should be treated as compatible (defensive)
        self.assertTrue(
            io_desc._check_minimum_python_version({"minimum_python_version": 3.10})
        )

        # None should be compatible
        self.assertTrue(
            io_desc._check_minimum_python_version({"minimum_python_version": None})
        )

        # Empty string should be compatible
        self.assertTrue(
            io_desc._check_minimum_python_version({"minimum_python_version": ""})
        )

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
        self,
        mock_find_cached,
        mock_get_manifest,
        mock_download,
        mock_exists,
        find_mock,
        find_one_mock,
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
