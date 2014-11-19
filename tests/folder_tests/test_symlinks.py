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
import sys
import unittest
import shutil
from mock import Mock
import tank
from tank_vendor import yaml
from tank import TankError
from tank import hook
from tank import folder
from tank_test.tank_test_base import *

         
class TestSymlinks(TankTestBase):
    """Test Symbolic link support."""
    def setUp(self):
        
        super(TestSymlinks, self).setUp()
        self.setup_fixtures("symlinks_core")
        
        self.shot_aaa = {"type": "Shot", 
                         "id": 1,
                         "code": "aaa",
                         "project": self.project}


        self.add_to_sg_mock_db([self.shot_aaa])

        self.aaa = os.path.join(self.project_root, "aaa")
        self.aaa_work = os.path.join(self.project_root, "aaa", "work")
        self.aaa_link = os.path.join(self.project_root, "aaa", "foo")
        


    def test_create_symlink(self):
        """
        Test folder creation for a shot which matches the static folder trigger condition
        """
        self.assertFalse(os.path.exists(self.aaa))
        self.assertFalse(os.path.exists(self.aaa_work))
        self.assertFalse(os.path.exists(self.aaa_link))
        

        folder.process_filesystem_structure(self.tk, 
                                            self.shot_aaa["type"], 
                                            self.shot_aaa["id"], 
                                            preview=False,
                                            engine=None)

        self.assertTrue(os.path.exists(self.aaa))
        self.assertTrue(os.path.exists(self.aaa_work))
        if sys.platform != "win32":
            self.assertTrue(os.path.lexists(self.aaa_link))
            self.assertTrue(os.path.islink(self.aaa_link))
            self.assertEquals(os.readlink(self.aaa_link), "../Stuff/project_code/aaa")
        else:
            # no support on windows
            self.assertFalse(os.path.exists(self.aaa_link))
        



        