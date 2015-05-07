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
import datetime

from mock import Mock, patch

import tank
from tank import context
from tank import TankError
from tank_test.tank_test_base import *
from tank.template import TemplatePath
from tank.templatekey import SequenceKey

def get_file_list_r(folder, tank_temp):
    items = []
    for x in os.listdir(folder):
        full_path = os.path.join(folder, x)
        test_centric_path = full_path[len(tank_temp):]
        # translate to platform agnostic path
        test_centric_path = test_centric_path.replace(os.path.sep, "/")
        items.append(test_centric_path)
        if os.path.isdir(full_path):
            items.extend(get_file_list_r(full_path, tank_temp))
    return items


class TestZipCore(TankTestBase):
    
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestZipCore, self).setUp()         
        self.zip_file_location = os.path.join(self.fixtures_root, "misc", "zip")
        

    def test_core(self):        
        
        import tank.deploy.zipfilehelper as zfh
        
        zip = os.path.join(self.zip_file_location, "tank_core.zip")
        txt = os.path.join(self.zip_file_location, "tank_core.txt")
        
        output_path = os.path.join(self.project_root, "core")
        
        zfh.unzip_file(zip, output_path)        
        zip_file_output = get_file_list_r(output_path, output_path)
        
        expected_output = open(txt).read().split("\n")
        
        self.maxDiff = None
        self.assertEqual(set(zip_file_output), set(expected_output))
        
        
class TestZipConfig(TankTestBase):
    
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestZipConfig, self).setUp()
        self.zip_file_location = os.path.join(self.fixtures_root, "misc", "zip")
        

    def test_config(self):        
        
        import tank.deploy.zipfilehelper as zfh
        
        zip = os.path.join(self.zip_file_location, "tk-config-default_v0.1.3.zip")
        txt = os.path.join(self.zip_file_location, "tk-config-default_v0.1.3.txt")
        
        output_path = os.path.join(self.project_root, "config")
        
        zfh.unzip_file(zip, output_path)        
        zip_file_output = get_file_list_r(output_path, output_path)

        expected_output = open(txt).read().split("\n")
        
        self.maxDiff = None
        self.assertEqual(set(zip_file_output), set(expected_output))


class TestZipApp(TankTestBase):
    
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestZipApp, self).setUp()
        self.zip_file_location = os.path.join(self.fixtures_root, "misc", "zip")

    def test_app(self):        
        
        import tank.deploy.zipfilehelper as zfh
        
        zip = os.path.join(self.zip_file_location, "tk-multi-about_v0.1.1.zip")
        txt = os.path.join(self.zip_file_location, "tk-multi-about_v0.1.1.txt")
        
        output_path = os.path.join(self.project_root, "app")
        
        zfh.unzip_file(zip, output_path)        
        zip_file_output = get_file_list_r(output_path, output_path)
        
        expected_output = open(txt).read().split("\n")
        
        self.maxDiff = None
        self.assertEqual(set(zip_file_output), set(expected_output))
