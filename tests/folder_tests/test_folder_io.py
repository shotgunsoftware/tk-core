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

                                
                                
class TestSchemaIOReceiver(TankTestBase):
    """Test the IO functionality."""
    
    
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestSchemaIOReceiver, self).setUp()
        self.setup_multi_root_fixtures()
        self.seq = {"type": "Sequence",
                    "id": 2,
                    "code": "seq_code",
                    "project": self.project}
        self.shot = {"type": "Shot",
                     "id": 1,
                     "code": "shot_code",
                     "sg_sequence": self.seq,
                     "project": self.project}
        self.step = {"type": "Step",
                     "id": 3,
                     "code": "step_code",
                     "short_name": "step_short_name"}
        self.asset = {"type": "Asset",
                    "id": 4,
                    "sg_asset_type": "assettype",
                    "code": "assetname",
                    "project": self.project}

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.shot, self.seq, self.step, self.project, self.asset])

        self.tk = tank.Tank(self.project_root)


    def test_primary_project_file(self):
        """
        Test that file with primary project path is written in the tank config area of 
        an alternative project path.
        """
        
        folder.process_filesystem_structure(self.tk, 
                                            self.project["type"], 
                                            self.project["id"], 
                                            preview=False,
                                            engine=None)        

        primary_file_path = os.path.join(self.alt_root_1, "tank", "config", "primary_project.yml")
        self.assertTrue(os.path.exists(primary_file_path))

        # test contents
        expected = {"windows_path": self.project_root,
                    "linux_path":self.project_root,
                    "mac_path":self.project_root}

        open_file = open(primary_file_path, "r")
        data = yaml.load(open_file)
        open_file.close()
        self.assertEqual(expected, data)

