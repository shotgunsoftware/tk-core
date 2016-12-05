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





class TestFolderConfiguration(TankTestBase):
    """
    Tests initialization of Schema class
    """
    def setUp(self):
        super(TestFolderConfiguration, self).setUp()
        self.schema_location = os.path.join(self.pipeline_config_root, "config", "core", "schema")

    def test_project_root_mismatch(self):
        """
        Case that root name specified in projects yml file does not exist in roots file.
        """
        # remove root name from the roots file
        self.setup_multi_root_fixtures()
        
        # should be fine
        folder.configuration.FolderConfiguration(self.tk, self.schema_location)

        roots_file = os.path.join(self.tk.pipeline_configuration.get_path(), "config", "core", "schema", "alternate_1.yml")
        
        fh = open(roots_file, "r")
        data = yaml.load(fh)
        fh.close()
        data["root_name"] = "some_bogus_Data"
        fh = open(roots_file, "w")
        fh.write(yaml.dump(data))
        fh.close()

        self.assertRaises(TankError,
                          folder.configuration.FolderConfiguration,
                          self.tk,
                          self.schema_location)

    def test_project_one_yml_missing(self):
        """
        Case that there are mutiple projects, one non-primary without yaml a file
        """
        self.setup_multi_root_fixtures()
                
        # should be fine
        folder.configuration.FolderConfiguration(self.tk, self.schema_location)
        
        project_yml = os.path.join(self.schema_location, "alternate_1.yml")
        os.remove(project_yml)
        
        self.assertRaises(TankError,
                          folder.configuration.FolderConfiguration,
                          self.tk,
                          self.schema_location)


