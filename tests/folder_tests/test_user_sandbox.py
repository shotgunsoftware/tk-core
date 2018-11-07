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
from mock import Mock, patch
import tank
from tank_vendor import yaml
from tank import TankError
from tank import hook
from tank import folder
from tank_test.tank_test_base import *


class TestHumanUser(TankTestBase):
    def setUp(self):
        super(TestHumanUser, self).setUp()
        
        self.setup_fixtures(parameters = {"core": "core.override/humanuser_core"})
        
        self.shot = {"type": "Shot",
                     "id": 1,
                     "code": "shot_code",
                     "project": self.project}

        self.humanuser = {"type": "HumanUser",
                          "name": "Mr Foo",
                          "id": 2,
                          "login": "foo"}

        self.humanuser2 = {"type": "HumanUser",
                          "id": 4,
                          "name": "Mr Bar",
                          "login": "bar"}

        self.add_to_sg_mock_db([self.shot, self.humanuser, self.humanuser2])

        self.user_path = os.path.join(self.project_root, "foo", "shot_code")
        self.user_path2 = os.path.join(self.project_root, "bar", "shot_code")

    @patch("tank.util.login.get_current_user")
    def test_not_made_default(self, get_current_user):

        self.assertFalse(os.path.exists(self.user_path))
        get_current_user.return_value = self.humanuser        
        folder.process_filesystem_structure(self.tk,
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine=None)
        self.assertFalse(os.path.exists(self.user_path))

    @patch("tank.util.login.get_current_user")
    def test_made_string(self, get_current_user):
        self.assertFalse(os.path.exists(self.user_path))
        
        get_current_user.return_value = self.humanuser
        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine="tk-maya")

        self.assertTrue(os.path.exists(self.user_path))
        
        get_current_user.return_value = self.humanuser2
        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine="tk-maya")

        self.assertTrue(os.path.exists(self.user_path2))

        # test user context
        ctx_foo = self.tk.context_from_path(self.user_path)        
        ctx_bar = self.tk.context_from_path(self.user_path2)
        
        self.assertEqual(ctx_foo.filesystem_locations, [self.user_path])
        self.assertEqual(ctx_bar.filesystem_locations, [self.user_path2])        
        
    @patch("tank.util.login.get_current_user")
    def test_login_not_in_shotgun(self, get_current_user):
        # make sure that if there is no loncal login matching, raise
        # an error when file system folders are created
        
        get_current_user.return_value = None 
        
        self.assertRaises(TankError,
                          folder.process_filesystem_structure,
                          self.tk,
                          self.shot["type"], 
                          self.shot["id"], 
                          preview=False,
                          engine="tk-maya")


