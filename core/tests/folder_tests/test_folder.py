"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------
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


#class Test_FieldsForFind(TankTestBase):
#    def setUp(self):
#
#        super(Test_FieldsForFind, self).setUp()
#        self.setup_fixtures()
#
#        schema_location = os.path.join(self.project_root, "tank", "config", "core", "schema")
#
#        # Mock rather than writing to disk
#        self.mock_make_folder = Mock()
#        self.mock_copy_file = Mock()
#        
#        self.tk = tank.Tank(self.project_root)
#
#        schema = Schema(self.tk, 
#                        schema_location, 
#                        self.mock_make_folder, 
#                        self.mock_copy_file,
#                        preview=False)
#        # we will just use any folder object
#        self.folder = schema.projects[0]
#
#    def test_project(self):
#        result = self.folder._fields_for_find()
#        self.assertIn("name", result)
#
#    def test_task(self):
#        self.folder.entity_type = "Task"
#        result = self.folder._fields_for_find()
#        self.assertIn("content", result)
#
#    def test_humanuser(self):
#        self.folder.entity_type = "HumanUser"
#        result = self.folder._fields_for_find()
#        self.assertIn("login", result)
#
#    def test_step(self):
#        self.folder.entity_type = "Step"
#        result = self.folder._fields_for_find()
#        self.assertIn("entity_type", result)
#
#    def test_other(self):
#        # any other entity...
#        self.folder.entity_type = "Other"
#        result = self.folder._fields_for_find()
#        self.assertIn("code", result)
#
#
