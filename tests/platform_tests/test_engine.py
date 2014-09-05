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
import unittest2 as unittest

from tank_test.tank_test_base import *

import tank
from tank.context import Context
from tank.platform import engine
from tank.errors import TankError


class TestStartEngine(TankTestBase):
    def setUp(self):
        super(TestStartEngine, self).setUp()
        self.setup_fixtures()
        
        # setup shot
        seq = {"type":"Sequence", "name":"seq_name", "id":3}
        seq_path = os.path.join(self.project_root, "sequences/Seq")
        self.add_production_path(seq_path, seq)
        shot = {"type":"Shot",
                "name": "shot_name",
                "id":2,
                "project": self.project}
        shot_path = os.path.join(seq_path, "shot_code")
        self.add_production_path(shot_path, shot)
        step = {"type":"Step", "name":"step_name", "id":4}
        self.shot_step_path = os.path.join(shot_path, "step_name")
        self.add_production_path(self.shot_step_path, step)
        
        
        self.test_resource = os.path.join(self.project_root, "tank", "config", "foo", "bar.png")
        os.makedirs(os.path.dirname(self.test_resource))
        fh = open(self.test_resource, "wt")
        fh.write("test")
        fh.close()
        
        
        self.context = self.tk.context_from_path(self.shot_step_path)

    def test_get_engine_path(self):
        engine_path = tank.platform.get_engine_path("test_engine", self.tk, self.context)
        expected_engine_path = os.path.join(self.project_root, "tank", "config", "test_engine")
        self.assertEquals(engine_path, expected_engine_path)

    def test_valid_engine(self):
        engine = tank.platform.start_engine("test_engine", self.tk, self.context)
        self.assertIsInstance(engine, tank.platform.engine.Engine)

    def test_engine_running(self):
        """Test calling start engine when a current engine already exists."""
        engine_name = "test_engine"
        engine = tank.platform.start_engine(engine_name, self.tk, self.context)
        self.assertRaises(TankError, tank.platform.start_engine, engine_name, self.tk, self.context)
    
    def tearDown(self):
        
        
        cur_engine = tank.platform.current_engine()
        if cur_engine:
            cur_engine.destroy()
        os.remove(self.test_resource)

        # important to call base class so it can clean up memory
        super(TestStartEngine, self).tearDown()


    def test_properties(self):
        """
        test engine properties
        """
        engine = tank.platform.start_engine("test_engine", self.tk, self.context)
        self.assertEqual(engine.name, "test_engine")
        self.assertEqual(engine.display_name, "test_engine")
        self.assertEqual(engine.version, "Undefined")
        self.assertEqual(engine.documentation_url, None)
        self.assertEqual(engine.instance_name, "test_engine")
        self.assertEqual(engine.context, self.context)
        
        
         
