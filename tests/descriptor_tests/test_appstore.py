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


from mock import patch

from tank_test.tank_test_base import TankTestBase, setUpModule

import sgtk
from sgtk.descriptor import Descriptor
from sgtk.descriptor.io_descriptor.base import IODescriptorBase
from sgtk.descriptor.descriptor import create_descriptor

from tank import TankError
from tank.platform.environment import InstalledEnvironment
from distutils.version import LooseVersion



class TestAppStoreLabels(TankTestBase):
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
