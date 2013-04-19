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


def login_foo():
    return "foo"

def login_bar():
    return "bar"


class TestHumanUser(TankTestBase):
    def setUp(self):
        super(TestHumanUser, self).setUp()
        self.setup_fixtures("humanuser_core")
        self.tk = tank.Tank(self.project_root)

        self.shot = {"type": "Shot",
                     "id": 1,
                     "code": "shot_code",
                     "project": self.project}

        self.humanuser = {"type": "HumanUser",
                          "id": 2,
                          "login": "foo"}

        self.humanuser2 = {"type": "HumanUser",
                          "id": 4,
                          "login": "bar"}

        self.add_to_sg_mock_db([self.shot, self.humanuser, self.humanuser2])

        self.user_path = os.path.join(self.project_root, "foo", "shot_code")
        self.user_path2 = os.path.join(self.project_root, "bar", "shot_code")

        self.TankCurLoginBackup = tank.util.login.get_login_name 

    def tearDown(self):
        tank.util.login.get_login_name = self.TankCurLoginBackup

    def test_not_made_default(self):
        
        self.assertFalse(os.path.exists(self.user_path))
        tank.util.login.g_shotgun_user_cache = "unknown"
        tank.util.login.get_login_name = login_foo

        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine=None)

        self.assertFalse(os.path.exists(self.user_path))


    def test_made_string(self):
        self.assertFalse(os.path.exists(self.user_path))
        
        tank.util.login.g_shotgun_user_cache = "unknown"
        tank.util.login.get_login_name = login_foo

        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine="tk-maya")

        self.assertTrue(os.path.exists(self.user_path))
        
        tank.util.login.g_shotgun_user_cache = "unknown"
        tank.util.login.get_login_name = login_bar        

        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine="tk-maya")

        self.assertTrue(os.path.exists(self.user_path2))

        # test user context
        ctx_foo = self.tk.context_from_path(self.user_path)        
        ctx_bar = self.tk.context_from_path(self.user_path2)
        
        self.assertEquals(ctx_foo.filesystem_locations, [self.user_path])
        self.assertEquals(ctx_bar.filesystem_locations, [self.user_path2])        
        
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


