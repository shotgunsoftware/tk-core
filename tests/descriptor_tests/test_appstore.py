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
import json

from mock import patch

from tank_test.tank_test_base import ShotgunTestBase, setUpModule # noqa

import sgtk
from sgtk.descriptor import Descriptor
from sgtk.descriptor.io_descriptor.base import IODescriptorBase
from sgtk.descriptor import create_descriptor

from tank import TankError
from tank.platform.environment import InstalledEnvironment
from distutils.version import LooseVersion


class TestAppStoreLabels(ShotgunTestBase):
    """
    Tests the app store io descriptor
    """

    def setUp(self):
        """
        Clear cached appstore connection
        """
        super(TestAppStoreLabels, self).setUp()

        # work around the app store connection lookup loops to just use std mockgun instance to mock the app store
        self._get_app_store_key_from_shotgun_mock = patch(
            "tank.descriptor.io_descriptor.appstore.IODescriptorAppStore._IODescriptorAppStore__create_sg_app_store_connection",
            return_value=(self.mockgun, None)
        )
        self._get_app_store_key_from_shotgun_mock.start()
        self.addCleanup(self._get_app_store_key_from_shotgun_mock.stop)

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find_one")
    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
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
                    'CustomNonProjectEntity13',
                    [['sg_system_name', 'is', 'tk-framework-main']],
                    ['id', 'sg_system_name', 'sg_status_list', 'sg_deprecation_message']
                )
            )

            return {
                "type": "CustomNonProjectEntity13",
                "id": 1234,
                "sg_system_name": "tk-framework-main",
                "sg_status_list": "prod",
                "sg_deprecation_message": None
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
            self.assertEqual(args, ('CustomNonProjectEntity09',))

            # app store is trying to be smart about bandwidth depending on queries, so limit may vary.
            kwargs["limit"] = None

            self.assertEqual(
                kwargs,
                {
                    'fields': [
                        'id', 'code', 'sg_status_list', 'description', 'tags', 'sg_detailed_release_notes',
                        'sg_documentation', 'sg_payload'
                    ],
                    'limit': None,
                    'order': [{'direction': 'desc', 'field_name': 'created_at'}],
                    'filters': [['sg_status_list', 'is_not', 'rev'], ['sg_status_list', 'is_not', 'bad'],
                                ['sg_tank_framework', 'is',
                                 {'sg_status_list': 'prod', 'type': 'CustomNonProjectEntity13', 'id': 1234,
                                  'sg_system_name': 'tk-framework-main',
                                  'sg_deprecation_message': None}]]
                }
            )

            return_data = []

            return_data.append(
                {
                    "type": "CustomNonProjectEntity09",
                    "id": 1,
                    "code": "v1.0.1",
                    "tags": [{"id": 1, "name": "2017.*", "type": "Tag"}, {"id": 2, "name": "2016.*", "type": "Tag"}],
                    "sg_detailed_release_notes": "Test 1",
                    "sg_status_list": "prod",
                    "description": "dummy",
                    "sg_detailed_release_notes": "dummy",
                    "sg_documentation": "dummy",
                    "sg_payload": {}
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
                    "sg_payload": {}
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
                    "sg_payload": {}
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
            {"name": "tk-framework-main", "version": "v1.0.0", "type": "app_store"}
        )
        self.assertEqual(desc.get_uri(), "sgtk:descriptor:app_store?name=tk-framework-main&version=v1.0.0")
        desc2 = desc.find_latest_version()
        self.assertEqual(desc2.get_uri(), "sgtk:descriptor:app_store?name=tk-framework-main&version=v3.0.1")

        # i am version 2016.3.45 so i am only getting 1.0.1
        desc = create_descriptor(
            None,
            Descriptor.FRAMEWORK,
            {"name": "tk-framework-main", "version": "v1.0.0", "type": "app_store", "label": "2016.3.45"}
        )
        self.assertEqual(
            desc.get_uri(),
            "sgtk:descriptor:app_store?label=2016.3.45&name=tk-framework-main&version=v1.0.0"
        )
        desc2 = desc.find_latest_version()
        self.assertEqual(
            desc2.get_uri(),
            "sgtk:descriptor:app_store?label=2016.3.45&name=tk-framework-main&version=v1.0.1"
        )

        # i am version 2017.3.45 so i am getting 2.0.1
        desc = create_descriptor(
            None,
            Descriptor.FRAMEWORK,
            {"name": "tk-framework-main", "version": "v1.0.0", "type": "app_store", "label": "2017.3.45"}
        )
        self.assertEqual(
            desc.get_uri(),
            "sgtk:descriptor:app_store?label=2017.3.45&name=tk-framework-main&version=v1.0.0"
        )
        desc2 = desc.find_latest_version()
        self.assertEqual(
            desc2.get_uri(),
            "sgtk:descriptor:app_store?label=2017.3.45&name=tk-framework-main&version=v2.0.1"
        )

        # i am version 2018.3.45 so i am getting 3.0.1
        desc = create_descriptor(
            None,
            Descriptor.FRAMEWORK,
            {"name": "tk-framework-main", "version": "v1.0.0", "type": "app_store", "label": "2018.3.45"}
        )
        self.assertEqual(
            desc.get_uri(),
            "sgtk:descriptor:app_store?label=2018.3.45&name=tk-framework-main&version=v1.0.0"
        )
        desc2 = desc.find_latest_version()
        self.assertEqual(
            desc2.get_uri(),
            "sgtk:descriptor:app_store?label=2018.3.45&name=tk-framework-main&version=v3.0.1"
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
            bundle_cache_root_override=root
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

    @patch("tank_vendor.shotgun_api3.Shotgun")
    @patch("urllib2.urlopen")
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
            if uri == 'http://unit_test_mock_sg/api3/sgtk_install_script':
                return MockResponse({"script_name": "bogus_script_name",
                                     "script_key": "bogus_script_key"}, 200)

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
