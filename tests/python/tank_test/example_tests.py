# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Example usage of tank test base.
"""

import os
import unittest2 as unittest
import tank

from tank_test.tank_test_base import TankTestBase, setUpModule, tearDownModule

class TestExample(TankTestBase):
    def setUp(self):
        # setup project
        super(TestExample, self).setUp()

        # setup config
        self.setup_fixtures()

        # add entities and their directories
        self.seq = {"type":"Sequence", "name":"seq_name", "id":3}
        self.seq_path = os.path.join(self.project_root, "sequence", "Seq")
        self.add_production_path(self.seq_path, self.seq)
        self.shot = {"type":"Shot", "name": "shot_name", "id":2}
        self.shot_path = os.path.join(self.project_root, "sequence", "Seq", "shot_2")
        self.add_production_path(self.shot_path, self.shot)

    def test_sg_query(self):
        # Show sg query
        result = self.sg_mock.find_one("Shot", [["id","is",2]])
        self.assertEquals(self.shot, result)

    def test_path_cache_get_paths(self):
        pc = tank.path_cache.PathCache(self.pipeline_configuration)
        result = pc.get_paths(self.shot["type"], self.shot["id"])
        self.assertEquals(self.shot_path, result[0])

    def test_path_cache_get_entity(self):
        pc = tank.path_cache.PathCache(self.pipeline_configuration)
        result = pc.get_entity(self.shot_path)
        self.assertEquals(self.shot, result)

    def test_context_from_path(self):
        shot_full_path = os.path.join(self.project_root, self.shot_path)
        tk = tank.Tank(self.project_root)
        ctx = tk.context_from_path(shot_full_path)
        self.assertEquals(self.shot, ctx.entity)

if __name__ == "__main__":
    unittest.main()

