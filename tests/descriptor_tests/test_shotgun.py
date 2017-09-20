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
from tank_test.tank_test_base import *

from tank_test.tank_test_base import TankTestBase, skip_if_git_missing

class TestShotgunIODescriptor(TankTestBase):
    """
    Testing the Shotgun IO descriptor
    """

    def setUp(self):
        """
        Sets up the next test's environment.
        """
        TankTestBase.setUp(self)

        self.bundle_cache = os.path.join(self.project_root, "bundle_cache")

    def test_construction(self):
        """
        Test validation and construction of shotgun descriptor
        """

        def _create_desc(location):
            return sgtk.descriptor.create_descriptor(
                self.tk.shotgun,
                sgtk.descriptor.Descriptor.APP,
                location
            )

        self.assertRaises(
            sgtk.descriptor.TankDescriptorError,
            _create_desc,
            {"type": "shotgun", "version": 123, "entity_type": "Shot", "field": "sg_field"}
        )

        self.assertRaises(
            sgtk.descriptor.TankDescriptorError,
            _create_desc,
            {"type": "shotgun", "version": 123, "field": "sg_field", "id": 123}
        )

        self.assertRaises(
            sgtk.descriptor.TankDescriptorError,
            _create_desc,
            {"type": "shotgun", "version": 123, "entity_type": "Shot", "field": "sg_field"}
        )

        self.assertRaises(
            sgtk.descriptor.TankDescriptorError,
            _create_desc,
            {"type": "shotgun", "entity_type": "Shot", "field": "sg_field", "id": 123}
        )

        # test entity id not nan
        self.assertRaises(
            sgtk.descriptor.TankDescriptorError,
            _create_desc,
            {"type": "shotgun", "version": 123, "entity_type": "Shot", "field": "sg_field", "id": "nan"}
        )

        # test version id not int
        self.assertRaises(
            sgtk.descriptor.TankDescriptorError,
            _create_desc,
            {"type": "shotgun", "version": "nan", "entity_type": "Shot", "field": "sg_field", "id": "123"}
        )

        # cannot specify both id and name
        self.assertRaises(
            sgtk.descriptor.TankDescriptorError,
            _create_desc,
            {"type": "shotgun", "version": 123, "entity_type": "Shot", "field": "sg_field", "id": 123, "name": "aaa123"}
        )

        # test project id not int
        self.assertRaises(
            sgtk.descriptor.TankDescriptorError,
            _create_desc,
            {"type": "shotgun", "version": 123, "entity_type": "Shot", "field": "sg_field", "project_id": "foo", "name": "aaa123"}
        )

        id_desc = _create_desc({
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

        name_desc = _create_desc({
            "type": "shotgun",
            "version": "123",
            "entity_type": "Shot",
            "field": "sg_field",
            "name": "aaa111"
            })

        self.assertEquals(name_desc.system_name, "aaa111")
        self.assertEquals(name_desc.version, "v123")

        name_proj_desc = _create_desc({
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
        expected_path = os.path.join(self.bundle_cache, "sg", "unit_test_mock_sg", "Shot.sg_field", "1234", "v123")

        def fake_download_attachment(*args):
            # assert that the expected download target is requested
            target_path = args[2]
            self.assertEqual(
                target_path,
                expected_path
            )
            sgtk.util.filesystem.ensure_folder_exists(target_path)

        _call_rpc_mock.side_effect = fake_download_attachment

        desc = sgtk.descriptor.create_descriptor(
            self.tk.shotgun,
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
    def test_resolve_project(self, _call_rpc_mock):
        """
        Test downloading descriptor based on name
        """
        expected_path = os.path.join(
            self.bundle_cache, "sg", "unit_test_mock_sg", "Shot.sg_field", "p123_aaa111", "v123"
        )

        def fake_download_attachment(*args):
            # assert that the expected download target is requested
            target_path = args[2]
            self.assertEqual(
                target_path,
                expected_path
            )
            sgtk.util.filesystem.ensure_folder_exists(target_path)

        _call_rpc_mock.side_effect = fake_download_attachment

        desc = sgtk.descriptor.create_descriptor(
            self.tk.shotgun,
            sgtk.descriptor.Descriptor.APP,
            {
                "type": "shotgun",
                "version": 123,
                "entity_type": "Shot",
                "field": "sg_field",
                "name": "aaa111",
                "project_id": 123
            },
            bundle_cache_root_override=self.bundle_cache
        )

        self.assertEquals(desc.get_path(), None)
        desc.ensure_local()
        self.assertEquals(desc.get_path(), expected_path)

    def test_get_latest(self):
        """
        Test resolcing la
        :return:
        """
        pass