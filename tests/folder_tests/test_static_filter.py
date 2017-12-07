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

         
class TestStaticFolderFilters(TankTestBase):
    """Test static folder filters."""
    def setUp(self):
        
        super(TestStaticFolderFilters, self).setUp()
        self.setup_fixtures(parameters = {"core": "core.override/static_filters_core"})
        
        self.shot_aaa = {"type": "Shot", 
                         "id": 1,
                         "code": "aaa",
                         "project": self.project}

        self.shot_bbb = {"type": "Shot", 
                         "id": 2,
                         "code": "bbb",
                         "project": self.project}

        self.add_to_sg_mock_db([self.shot_aaa, self.shot_bbb])

        self.aaa = os.path.join(self.project_root, "aaa")
        self.aaa_work = os.path.join(self.project_root, "aaa", "work")
        self.aaa_pub = os.path.join(self.project_root, "aaa", "publish")
        
        self.bbb = os.path.join(self.project_root, "bbb")
        self.bbb_work = os.path.join(self.project_root, "bbb", "work")
        self.bbb_pub = os.path.join(self.project_root, "bbb", "publish")


    def test_create_with_filter_triggering(self):
        """
        Test folder creation for a shot which matches the static folder trigger condition
        """
        self.assertFalse(os.path.exists(self.aaa))
        self.assertFalse(os.path.exists(self.aaa_work))
        self.assertFalse(os.path.exists(self.aaa_pub))

        folder.process_filesystem_structure(self.tk, 
                                            self.shot_aaa["type"], 
                                            self.shot_aaa["id"], 
                                            preview=False,
                                            engine=None)

        self.assertTrue(os.path.exists(self.aaa))
        self.assertTrue(os.path.exists(self.aaa_work))
        self.assertTrue(os.path.exists(self.aaa_pub))


    def test_create_with_no_filter_triggering(self):
        """
        Test folder creation for a shot which does not match the static folder trigger condition
        """
        self.assertFalse(os.path.exists(self.bbb))
        self.assertFalse(os.path.exists(self.bbb_work))
        self.assertFalse(os.path.exists(self.bbb_pub))

        folder.process_filesystem_structure(self.tk, 
                                            self.shot_bbb["type"], 
                                            self.shot_bbb["id"], 
                                            preview=False,
                                            engine=None)

        self.assertTrue(os.path.exists(self.bbb))
        self.assertTrue(os.path.exists(self.bbb_work))
        self.assertFalse(os.path.exists(self.bbb_pub))

        
