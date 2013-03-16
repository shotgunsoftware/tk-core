"""
Copyright (c) 2012 Shotgun Software, Inc
"""
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
        self.tk = tank.Tank(self.project_root)
        self.schema_location = os.path.join(self.project_root, "tank", "config", "core", "schema")

    def test_project_missing(self):
        """Case that project directory is missing from schema"""
        self.setup_fixtures()
        
        # should be fine
        folder.configuration.FolderConfiguration(self.tk, self.schema_location)
        
        project_schema = os.path.join(self.project_root, "tank", "config", "core", "schema", "project")
        shutil.rmtree(project_schema)
        
        self.assertRaises(TankError, folder.configuration.FolderConfiguration, self.tk, self.schema_location)

    def test_project_root_mismatch(self):
        """
        Case that root name specified in projects yml file does not exist in roots file.
        """
        # remove root name from the roots file
        self.setup_multi_root_fixtures()
        
        # should be fine
        folder.configuration.FolderConfiguration(self.tk, self.schema_location)
        
        project_name = os.path.basename(self.project_root)
        
        roots_path = tank.constants.get_roots_file_location(self.pipeline_configuration_path)        
        roots_file = open(roots_path, "r")
        roots = yaml.load(roots_file)
        roots_file.close()
        del(roots["alternate_1"])

        roots_file = open(roots_path, "w")
        roots_file.write(yaml.dump(roots))
        roots_file.close()

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


