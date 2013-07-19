# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import unittest
import shutil
from mock import Mock
import tank
from tank_vendor import yaml
from tank import TankError
from tank import hook
from tank import folder
from tank_test.tank_test_base import *

         
class TestDeferredFolderCreation(TankTestBase):
    """Test deferring of folder creation."""
    def setUp(self):
        super(TestDeferredFolderCreation, self).setUp()
        self.setup_fixtures("deferred_core")
        self.tk = tank.Tank(self.project_root)

        self.shot = {"type": "Shot", 
                     "id": 1,
                     "code": "shot_code",
                     "project": self.project}

        self.asset = {"type": "Asset",
                    "id": 4,
                    "sg_asset_type": "assettype",
                    "code": "assetname",
                    "project": self.project}

        self.add_to_sg_mock_db([self.shot, self.asset])

        # add mock schema data so that a list of the asset type enum values can be returned
        data = {}
        data["properties"] = {}
        data["properties"]["valid_values"] = {}
        data["properties"]["valid_values"]["value"] = ["assettype"]
        self.add_to_sg_schema_db("Asset", "sg_asset_type", data)

        self.deferred_absent = os.path.join(self.project_root, "deferred_absent", "shot_code")
        self.deferred_false = os.path.join(self.project_root, "deferred_false", "shot_code")
        self.deferred_specified = os.path.join(self.project_root, "deferred_specified", "shot_code")
        self.deferred_specified_2 = os.path.join(self.project_root, "deferred_specified_2", "shot_code")
        self.deferred_true = os.path.join(self.project_root, "deferred_true", "shot_code")
        self.deferred_asset_type = os.path.join(self.project_root, "assettype")
        self.deferred_asset = os.path.join(self.deferred_asset_type, "assetname")

    def test_option_absent(self):
        self.assertFalse(os.path.exists(self.deferred_absent))
        self.assertFalse(os.path.exists(self.deferred_false))
        self.assertFalse(os.path.exists(self.deferred_specified))
        self.assertFalse(os.path.exists(self.deferred_specified_2))
        self.assertFalse(os.path.exists(self.deferred_true))
        self.assertFalse(os.path.exists(self.deferred_asset_type))
        self.assertFalse(os.path.exists(self.deferred_asset))

        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine=None)

        self.assertTrue(os.path.exists(self.deferred_absent))
        self.assertTrue(os.path.exists(self.deferred_false))
        self.assertFalse(os.path.exists(self.deferred_specified))
        self.assertFalse(os.path.exists(self.deferred_specified_2))
        self.assertFalse(os.path.exists(self.deferred_true))
        self.assertFalse(os.path.exists(self.deferred_asset_type))
        self.assertFalse(os.path.exists(self.deferred_asset))


    def test_specify_option(self):
        self.assertFalse(os.path.exists(self.deferred_absent))
        self.assertFalse(os.path.exists(self.deferred_false))
        self.assertFalse(os.path.exists(self.deferred_specified))
        self.assertFalse(os.path.exists(self.deferred_specified_2))
        self.assertFalse(os.path.exists(self.deferred_true))
        self.assertFalse(os.path.exists(self.deferred_asset_type))
        self.assertFalse(os.path.exists(self.deferred_asset))

        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine="specific_1")

        self.assertTrue(os.path.exists(self.deferred_absent))
        self.assertTrue(os.path.exists(self.deferred_false))
        self.assertTrue(os.path.exists(self.deferred_specified))
        self.assertFalse(os.path.exists(self.deferred_specified_2))
        self.assertTrue(os.path.exists(self.deferred_true))
        self.assertFalse(os.path.exists(self.deferred_asset_type))
        self.assertFalse(os.path.exists(self.deferred_asset))

    def test_specify_option_2(self):

        self.assertFalse(os.path.exists(self.deferred_absent))
        self.assertFalse(os.path.exists(self.deferred_false))
        self.assertFalse(os.path.exists(self.deferred_specified))
        self.assertFalse(os.path.exists(self.deferred_specified_2))
        self.assertFalse(os.path.exists(self.deferred_true))
        self.assertFalse(os.path.exists(self.deferred_asset_type))
        self.assertFalse(os.path.exists(self.deferred_asset))

        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine="specific_2")

        self.assertTrue(os.path.exists(self.deferred_absent))
        self.assertTrue(os.path.exists(self.deferred_false))
        self.assertTrue(os.path.exists(self.deferred_specified))
        self.assertTrue(os.path.exists(self.deferred_specified_2))
        self.assertTrue(os.path.exists(self.deferred_true))
        self.assertFalse(os.path.exists(self.deferred_asset_type))
        self.assertFalse(os.path.exists(self.deferred_asset))


    def test_list_field(self):

        self.assertFalse(os.path.exists(self.deferred_absent))
        self.assertFalse(os.path.exists(self.deferred_false))
        self.assertFalse(os.path.exists(self.deferred_specified))
        self.assertFalse(os.path.exists(self.deferred_specified_2))
        self.assertFalse(os.path.exists(self.deferred_true))
        self.assertFalse(os.path.exists(self.deferred_asset_type))
        self.assertFalse(os.path.exists(self.deferred_asset))

        folder.process_filesystem_structure(self.tk, 
                                            self.asset["type"], 
                                            self.asset["id"], 
                                            preview=False,
                                            engine="asset_type")

        self.assertFalse(os.path.exists(self.deferred_absent))
        self.assertFalse(os.path.exists(self.deferred_false))
        self.assertFalse(os.path.exists(self.deferred_specified))
        self.assertFalse(os.path.exists(self.deferred_specified_2))
        self.assertFalse(os.path.exists(self.deferred_true))
        self.assertTrue(os.path.exists(self.deferred_asset_type))
        self.assertFalse(os.path.exists(self.deferred_asset))


    def test_asset(self):

        self.assertFalse(os.path.exists(self.deferred_absent))
        self.assertFalse(os.path.exists(self.deferred_false))
        self.assertFalse(os.path.exists(self.deferred_specified))
        self.assertFalse(os.path.exists(self.deferred_specified_2))
        self.assertFalse(os.path.exists(self.deferred_true))
        self.assertFalse(os.path.exists(self.deferred_asset_type))
        self.assertFalse(os.path.exists(self.deferred_asset))

        folder.process_filesystem_structure(self.tk, 
                                            self.asset["type"], 
                                            self.asset["id"], 
                                            preview=False,
                                            engine="asset")

        self.assertFalse(os.path.exists(self.deferred_absent))
        self.assertFalse(os.path.exists(self.deferred_false))
        self.assertFalse(os.path.exists(self.deferred_specified))
        self.assertFalse(os.path.exists(self.deferred_specified_2))
        self.assertFalse(os.path.exists(self.deferred_true))
        self.assertTrue(os.path.exists(self.deferred_asset_type))
        self.assertTrue(os.path.exists(self.deferred_asset))



