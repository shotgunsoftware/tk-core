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

from . import assert_paths_to_create, execute_folder_creation_proxy


# test secondary entities.

class TestSchemaCreateFoldersSecondaryEntity(TankTestBase):
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestSchemaCreateFoldersSecondaryEntity, self).setUp()
        
        self.setup_fixtures("optional_folder_fields")
        
        self.shot = {"type": "Shot",
                     "id": 1,
                     "code": "shot_code",
                     "sg_other_field": None,
                     "project": self.project}

        entities = [self.shot, 
                    self.project]

        # Add these to mocked shotgun
        self.add_to_sg_mock_db(entities)

        self.schema_location = os.path.join(self.project_root, "tank", "config", "core", "schema")

        self.FolderIOReceiverBackup = folder.folder_io.FolderIOReceiver.execute_folder_creation
        folder.folder_io.FolderIOReceiver.execute_folder_creation = execute_folder_creation_proxy

    def tearDown(self):
        
        folder.folder_io.FolderIOReceiver.execute_folder_creation = self.FolderIOReceiverBackup


    def test_other_is_none(self):
        """
        sg_other_field is none and forces folder creation to disregard optional path segment
        """
        expected_paths = []
        shot_path = os.path.join(self.project_root, "%s" % self.shot["code"])
        expected_paths.extend( [self.project_root, shot_path] )

        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine=None)        
        
        assert_paths_to_create(expected_paths)


    def test_other_isnt_none(self):
        """
        sg_other_field is not none and full expression is used. 
        """
        expected_paths = []
        self.shot["sg_other_field"] = "xxx"
        shot_path = os.path.join(self.project_root, "%s_%s" % (self.shot["code"], self.shot["sg_other_field"]))
        expected_paths.extend( [self.project_root, shot_path] )

        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine=None)        
        
        assert_paths_to_create(expected_paths)



