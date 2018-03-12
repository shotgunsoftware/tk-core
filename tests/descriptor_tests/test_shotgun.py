# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

import sgtk
from mock import patch
from tank_test.tank_test_base import ShotgunTestBase, setUpModule # noqa


class TestShotgunIODescriptor(ShotgunTestBase):
    """
    Testing the Shotgun IO descriptor
    """

    def setUp(self):
        """
        Sets up the next test's environment.
        """
        ShotgunTestBase.setUp(self)

        self.bundle_cache = os.path.join(self.project_root, "bundle_cache")

    def _create_desc(self, location):
        """Helper method"""
        return sgtk.descriptor.create_descriptor(
            self.mockgun,
            sgtk.descriptor.Descriptor.APP,
            location
        )

    def test_construction_validation(self):
        """
        Test validation of shotgun descriptor
        """
        def _test_raises_error(location):
            self.assertRaises(
                sgtk.descriptor.TankDescriptorError,
                self._create_desc,
                location
            )

        # test all required parameters are provided
        _test_raises_error({"type": "shotgun", "version": 123, "entity_type": "Shot", "field": "sg_field"})
        _test_raises_error({"type": "shotgun", "version": 123, "field": "sg_field", "id": 123})
        _test_raises_error({"type": "shotgun", "version": 123, "entity_type": "Shot", "field": "sg_field"})
        _test_raises_error({"type": "shotgun", "entity_type": "Shot", "field": "sg_field", "id": 123})

        # test entity id not nan
        _test_raises_error({"type": "shotgun", "version": 123, "entity_type": "Shot", "field": "sg_field", "id": "nan"})

        # test version id not int
        _test_raises_error(
            {"type": "shotgun", "version": "nan", "entity_type": "Shot", "field": "sg_field", "id": "123"}
        )

        # cannot specify both id and name
        _test_raises_error(
            {"type": "shotgun", "version": 123, "entity_type": "Shot", "field": "sg_field", "id": 123, "name": "aaa123"}
        )

        # test project id not int
        _test_raises_error(
            {
                "type": "shotgun", "version": 123, "entity_type": "Shot",
                "field": "sg_field", "project_id": "foo", "name": "aaa123"
            }
        )

    def test_construction_by_id(self):
        """
        Test construction of shotgun descriptor by name
        """
        # test construction by name
        id_desc = self._create_desc({
            "type": "shotgun",
            "version": 123,
            "entity_type": "Shot",
            "field": "sg_field",
            "id": 1234
        })
        self.assertEquals(id_desc.system_name, "Shot_1234")
        self.assertEquals(id_desc.version, "v123")
        self.assertEquals(id_desc.is_dev(), False)
        self.assertEquals(id_desc.is_immutable(), True)

    def test_construction_by_name(self):
        """
        Test construction of shotgun descriptor by name
        """
        # test construction by id
        name_desc = self._create_desc({
            "type": "shotgun",
            "version": "123",
            "entity_type": "Shot",
            "field": "sg_field",
            "name": "aaa111"
        })

        self.assertEquals(name_desc.system_name, "aaa111")
        self.assertEquals(name_desc.version, "v123")

        name_proj_desc = self._create_desc({
            "type": "shotgun",
            "version": 123,
            "entity_type": "Shot",
            "field": "sg_field",
            "name": "aaa111",
            "project_id": 22
        })

        self.assertEquals(name_proj_desc.system_name, "p22_aaa111")
        self.assertEquals(name_proj_desc.version, "v123")

    @patch("sgtk.util.shotgun.download_and_unpack_attachment")
    def test_resolve_id(self, _call_rpc_mock):
        """
        Test downloading shotgun descriptor based on id
        """
        expected_path = os.path.join(self.bundle_cache, "sg", "unit_test_mock_sg", "v123")

        def fake_download_attachment(*args, **kwargs):
            # assert that the expected download target is requested
            target_path = args[2]
            sgtk.util.filesystem.ensure_folder_exists(target_path)

        _call_rpc_mock.side_effect = fake_download_attachment

        desc = sgtk.descriptor.create_descriptor(
            self.mockgun,
            sgtk.descriptor.Descriptor.APP,
            {
                "type": "shotgun",
                "version": 123,
                "entity_type": "Shot",
                "field": "sg_field",
                "id": 1234
            },
            bundle_cache_root_override=self.bundle_cache
        )

        self.assertEquals(desc.get_path(), None)
        desc.ensure_local()
        self.assertEquals(desc.get_path(), expected_path)

    @patch("sgtk.util.shotgun.download_and_unpack_attachment")
    def test_resolve_name_and_project(self, _call_rpc_mock):
        """
        Test downloading descriptor based on name
        """
        expected_path = os.path.join(
            self.bundle_cache, "sg", "unit_test_mock_sg", "v124"
        )

        def fake_download_attachment(*args, **kwargs):
            # assert that the expected download target is requested
            target_path = args[2]
            sgtk.util.filesystem.ensure_folder_exists(target_path)

        _call_rpc_mock.side_effect = fake_download_attachment

        desc = sgtk.descriptor.create_descriptor(
            self.mockgun,
            sgtk.descriptor.Descriptor.APP,
            {
                "type": "shotgun",
                "version": 124,
                "entity_type": "Shot",
                "field": "sg_field",
                "name": "bbb111",
                "project_id": 123
            },
            bundle_cache_root_override=self.bundle_cache
        )

        self.assertEquals(desc.get_path(), None)
        desc.ensure_local()
        self.assertEquals(desc.get_path(), expected_path)

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_get_latest_by_id(self, find_mock):
        """
        Tests resolving the latest descriptor based on id
        """
        def our_find_mock(*args, **kwargs):
            self.assertEquals(
                args,
                ('Shot', [['id', 'is', 456]])
            )
            self.assertEquals(
                kwargs,
                {'retired_only': False, 'fields': ['sg_field'], 'filter_operator': None, 'order': None}
            )

            return [{
                "type": "Shot",
                "id": 456,
                "sg_field": {
                    'name': 'v1.2.3.zip',
                    'url': 'https://sg-media-usor-01.s3.amazonaws.com/foo/bar',
                    'content_type': 'application/zip',
                    'type': 'Attachment',
                    'id': 139,
                    'link_type': 'upload'
                }
            }]

        find_mock.side_effect = our_find_mock

        desc = sgtk.descriptor.create_descriptor(
            self.mockgun,
            sgtk.descriptor.Descriptor.APP,
            {
                "type": "shotgun",
                "version": 0,
                "entity_type": "Shot",
                "field": "sg_field",
                "id": 456,
            },
            bundle_cache_root_override=self.bundle_cache
        )

        self.assertEquals(desc.version, "v0")
        latest_desc = desc.find_latest_version()
        self.assertEquals(latest_desc.version, "v139")

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_get_latest_by_name(self, find_mock):
        """
        Tests resolving the latest descriptor based on name
        """
        def our_find_mock(*args, **kwargs):
            self.assertEquals(
                args,
                ('Shot', [['code', 'is', 'Primary']])
            )
            self.assertEquals(
                kwargs,
                {'retired_only': False, 'fields': ['sg_field'], 'filter_operator': None, 'order': None}
            )

            return [{
                "type": "Shot",
                "id": 456,
                "sg_field": {
                    'name': 'v1.2.3.zip',
                    'url': 'https://sg-media-usor-01.s3.amazonaws.com/foo/bar',
                    'content_type': 'application/zip',
                    'type': 'Attachment',
                    'id': 139,
                    'link_type': 'upload'
                }
            }]

        find_mock.side_effect = our_find_mock

        desc = sgtk.descriptor.create_descriptor(
            self.mockgun,
            sgtk.descriptor.Descriptor.APP,
            {
                "type": "shotgun",
                "version": 0,
                "entity_type": "Shot",
                "field": "sg_field",
                "name": "Primary",
            },
            bundle_cache_root_override=self.bundle_cache
        )

        self.assertEquals(desc.version, "v0")
        latest_desc = desc.find_latest_version()
        self.assertEquals(latest_desc.version, "v139")

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_get_latest_by_name_and_proj(self, find_mock):
        """
        Tests resolving the latest descriptor based on name and project
        """
        def our_find_mock(*args, **kwargs):
            self.assertEquals(
                args,
                ('Shot', [['code', 'is', 'Primary'], ['project', 'is', {'type': 'Project', 'id': 1334}]])
            )
            self.assertEquals(
                kwargs,
                {'retired_only': False, 'fields': ['sg_field'], 'filter_operator': None, 'order': None}
            )

            return [{
                "type": "Shot",
                "id": 456,
                "sg_field": {
                    'name': 'v1.2.3.zip',
                    'url': 'https://sg-media-usor-01.s3.amazonaws.com/foo/bar',
                    'content_type': 'application/zip',
                    'type': 'Attachment',
                    'id': 139,
                    'link_type': 'upload'
                }
            }]

        find_mock.side_effect = our_find_mock

        desc = sgtk.descriptor.create_descriptor(
            self.mockgun,
            sgtk.descriptor.Descriptor.APP,
            {
                "type": "shotgun",
                "version": 0,
                "entity_type": "Shot",
                "field": "sg_field",
                "name": "Primary",
                "project_id": 1334,
            },
            bundle_cache_root_override=self.bundle_cache
        )

        self.assertEquals(desc.version, "v0")
        latest_desc = desc.find_latest_version()
        self.assertEquals(latest_desc.version, "v139")

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_find_invalid_attachment(self, find_mock):
        """
        Tests resolving an attachment which doesn't have an uploaded attachment
        """
        def our_find_mock(*args, **kwargs):
            return [{
                "type": "Shot",
                "id": 456,
                "sg_field": {
                    'name': 'v1.2.3.zip',
                    'url': 'https://sg-media-usor-01.s3.amazonaws.com/foo/bar',
                    'content_type': 'application/zip',
                    'type': 'Attachment',
                    'id': 139,
                    'link_type': 'url'
                }
            }]

        find_mock.side_effect = our_find_mock

        desc = sgtk.descriptor.create_descriptor(
            self.mockgun,
            sgtk.descriptor.Descriptor.APP,
            {
                "type": "shotgun",
                "version": 0,
                "entity_type": "Shot",
                "field": "sg_field",
                "id": 456,
            },
            bundle_cache_root_override=self.bundle_cache
        )

        self.assertEquals(desc.version, "v0")
        self.assertRaises(sgtk.descriptor.TankDescriptorError, desc.find_latest_version)

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_missing_record(self, find_mock):
        """
        Tests behavior when a shotgun record is missing
        """
        def our_find_mock(*args, **kwargs):
            # nothing in shotgun
            return []

        find_mock.side_effect = our_find_mock

        desc = sgtk.descriptor.create_descriptor(
            self.mockgun,
            sgtk.descriptor.Descriptor.APP,
            {
                "type": "shotgun",
                "version": 0,
                "entity_type": "Shot",
                "field": "sg_field",
                "id": 456,
            },
            bundle_cache_root_override=self.bundle_cache
        )

        self.assertEquals(desc.version, "v0")
        self.assertRaises(
            sgtk.descriptor.TankDescriptorError,
            desc.find_latest_version
        )

    def test_get_latest_cached_by_name(self):
        """
        Tests resolving locally cached items by name
        """
        os.makedirs(
            os.path.join(self.bundle_cache, "sg", "unit_test_mock_sg", "v99")
        )

        desc = sgtk.descriptor.create_descriptor(
            self.mockgun,
            sgtk.descriptor.Descriptor.APP,
            {
                "type": "shotgun",
                "version": 99,
                "entity_type": "Shot",
                "field": "sg_field",
                "name": "aaa111",
                "project_id": 123
            },
            bundle_cache_root_override=self.bundle_cache
        )

        self.assertEquals(desc.version, "v99")
        latest_cached = desc.find_latest_cached_version()
        self.assertEquals(latest_cached.version, "v99")

        desc = sgtk.descriptor.create_descriptor(
            self.mockgun,
            sgtk.descriptor.Descriptor.APP,
            {
                "type": "shotgun",
                "version": 1,
                "entity_type": "Shot",
                "field": "sg_field",
                "name": "aaa111",
                "project_id": 123
            },
            bundle_cache_root_override=self.bundle_cache
        )

        self.assertEquals(desc.version, "v1")
        latest_cached = desc.find_latest_cached_version()
        self.assertEquals(latest_cached, None)

    def test_get_latest_cached_by_id(self):
        """
        Tests resolving locally cached items by id
        """
        os.makedirs(
            os.path.join(self.bundle_cache, "sg", "unit_test_mock_sg", "v98")
        )

        desc = sgtk.descriptor.create_descriptor(
            self.mockgun,
            sgtk.descriptor.Descriptor.APP,
            {
                "type": "shotgun",
                "version": 98,
                "entity_type": "Shot",
                "field": "sg_field",
                "id": 567
            },
            bundle_cache_root_override=self.bundle_cache
        )

        self.assertEquals(desc.version, "v98")
        latest_cached = desc.find_latest_cached_version()
        self.assertEquals(latest_cached.version, "v98")

        desc = sgtk.descriptor.create_descriptor(
            self.mockgun,
            sgtk.descriptor.Descriptor.APP,
            {
                "type": "shotgun",
                "version": 1,
                "entity_type": "Shot",
                "field": "sg_field",
                "id": 567
            },
            bundle_cache_root_override=self.bundle_cache
        )

        self.assertEquals(desc.version, "v1")
        latest_cached = desc.find_latest_cached_version()
        self.assertEquals(latest_cached, None)
