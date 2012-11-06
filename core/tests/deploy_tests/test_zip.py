"""
Copyright (c) 2012 Shotgun Software, Inc
"""
import os
import datetime

from mock import Mock, patch

import tank
from tank import context
from tank import TankError
from tank_test.tank_test_base import *
from tank.template import TemplatePath
from tank.templatekey import SequenceKey


class TestZip(TankTestBase):
    
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestZip, self).setUp()
        
        self.zip_file_location = os.path.join(self.tank_source_path, "core", "tests", "data", "zip")

    def _get_file_list_r(self, folder):
        items = []
        for x in os.listdir(folder):
            full_path = os.path.join(folder, x)
            test_centric_path = full_path[len(self.tank_temp):]
            # translate to platform agnostic path
            test_centric_path = test_centric_path.replace(os.path.sep, "/")
            items.append(test_centric_path)
            if os.path.isdir(full_path):
                items.extend(self._get_file_list_r(full_path))
        return items
        

    def test_core(self):        
        
        import tank.deploy.zipfilehelper as zfh
        
        zip = os.path.join(self.zip_file_location, "tank_core.zip")
        txt = os.path.join(self.zip_file_location, "tank_core.txt")
        
        output_path = os.path.join(self.tank_temp, "core")
        
        zfh.unzip_file(zip, output_path)        
        zip_file_output = self._get_file_list_r(output_path)
        
        expected_output = open(txt).read().split("\n")
        
        self.maxDiff = None
        self.assertEqual(set(zip_file_output), set(expected_output))
        

    def test_config(self):        
        
        import tank.deploy.zipfilehelper as zfh
        
        zip = os.path.join(self.zip_file_location, "tk-config-default_v0.1.3.zip")
        txt = os.path.join(self.zip_file_location, "tk-config-default_v0.1.3.txt")
        
        output_path = os.path.join(self.tank_temp, "config")
        
        zfh.unzip_file(zip, output_path)        
        zip_file_output = self._get_file_list_r(output_path)

        expected_output = open(txt).read().split("\n")
        
        self.maxDiff = None
        self.assertEqual(set(zip_file_output), set(expected_output))


    def test_app(self):        
        
        import tank.deploy.zipfilehelper as zfh
        
        zip = os.path.join(self.zip_file_location, "tk-multi-about_v0.1.1.zip")
        txt = os.path.join(self.zip_file_location, "tk-multi-about_v0.1.1.txt")
        
        output_path = os.path.join(self.tank_temp, "app")
        
        zfh.unzip_file(zip, output_path)        
        zip_file_output = self._get_file_list_r(output_path)
        
        expected_output = open(txt).read().split("\n")
        
        self.maxDiff = None
        self.assertEqual(set(zip_file_output), set(expected_output))
