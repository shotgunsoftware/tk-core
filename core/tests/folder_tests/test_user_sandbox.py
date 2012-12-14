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




class TestHumanUser(TankTestBase):
    def setUp(self):
        super(TestHumanUser, self).setUp()
        self.setup_fixtures("humanuser_core")
        self.tk = tank.Tank(self.project_root)

        self.shot = {"type": "Shot",
                     "id": 1,
                     "code": "shot_code",
                     "project": self.project}

        cur_login = tank.util.login.get_login_name()
        
        self.humanuser = {"type": "HumanUser",
                          "id": 2,
                          "login": cur_login}

        self.add_to_sg_mock_db([self.shot, self.humanuser])

        self.user_path = os.path.join(self.project_root, cur_login, "shot_code")

    def test_not_made_default(self):
        self.assertFalse(os.path.exists(self.user_path))

        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine=None)

        self.assertFalse(os.path.exists(self.user_path))


    def test_made_string(self):
        self.assertFalse(os.path.exists(self.user_path))

        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine="tk-maya")

        self.assertTrue(os.path.exists(self.user_path))


    def test_login_not_in_shotgun(self):
        # make sure that if there is no loncal login matching, raise
        # an error when file system folders are created
        
        
        # change the record in the mock db to not match the local login
        self.humanuser["login"] = "not the local login"

        self.assertRaises(TankError,
                          folder.process_filesystem_structure,
                          self.tk,
                          self.shot["type"], 
                          self.shot["id"], 
                          preview=False,
                          engine="tk-maya")


