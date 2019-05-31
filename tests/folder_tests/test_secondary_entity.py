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
from mock import Mock
import tank
from tank_vendor import yaml
from tank import TankError
from tank import hook
from tank import path_cache
from tank import folder
from tank_test.tank_test_base import *

from . import assert_paths_to_create, execute_folder_creation_proxy

# test secondary entities.

class TestSchemaCreateFoldersSecondaryEntity(TankTestBase):
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestSchemaCreateFoldersSecondaryEntity, self).setUp()
        
        self.setup_fixtures(parameters = {"core": "core.override/secondary_entity"})
        
        self.seq = {"type": "Sequence",
                    "id": 2,
                    "code": "seq_code",
                    "project": self.project}
        self.shot = {"type": "Shot",
                     "id": 1,
                     "code": "shot_code",
                     "sg_sequence": self.seq,
                     # DODGY - remove when we replace the crappy sg test mocker with mockgun
                     "sg_sequence.Sequence.code": self.seq["code"],
                     "project": self.project}
        self.step = {"type": "Step",
                     "id": 3,
                     "code": "step_code",
                     "short_name": "step_short_name"}

        self.step2 = {"type": "Step",
                     "id": 33,
                     "code": "step_code_2",
                     "short_name": "step_short_name_2"}
        
        self.asset = {"type": "Asset",
                    "id": 4,
                    "sg_asset_type": "assettype",
                    "code": "assetname",
                    "project": self.project}
        
        self.task = {"type": "Task",
                     "id": 23,
                     "entity": self.shot,
                     "step": self.step,
                     # DODGY - remove when we replace the crappy sg test mocker with mockgun
                     "step.Step.short_name": self.step["short_name"],
                     "content": "task1",
                     "project": self.project}

        self.task2 = {"type": "Task",
                     "id": 25,
                     "entity": self.shot,
                     "step": self.step2,
                     # DODGY - remove when we replace the crappy sg test mocker with mockgun
                     "step.Step.short_name": self.step2["short_name"],
                     "content": "task2",
                     "project": self.project}

        entities = [self.shot, 
                    self.seq, 
                    self.step,
                    self.step2, 
                    self.project, 
                    self.asset, 
                    self.task,
                    self.task2]

        # Add these to mocked shotgun
        self.add_to_sg_mock_db(entities)

        self.schema_location = os.path.join(self.pipeline_config_root, "config", "core", "schema")

        self.FolderIOReceiverBackup = folder.folder_io.FolderIOReceiver.execute_folder_creation
        folder.folder_io.FolderIOReceiver.execute_folder_creation = execute_folder_creation_proxy

    def tearDown(self):
        # important to call base class so it can clean up memory
        super(TestSchemaCreateFoldersSecondaryEntity, self).tearDown()
        
        # and do local teardown                                        
        folder.folder_io.FolderIOReceiver.execute_folder_creation = self.FolderIOReceiverBackup


    def test_shot(self):
        """Tests paths used in making a shot are as expected."""
        
        expected_paths = []
        shot_path = os.path.join(self.project_root, "%s_%s" % (self.shot["code"], self.seq["code"]))
        expected_paths.extend( [self.project_root, shot_path] )

        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine=None)        
        
        assert_paths_to_create(expected_paths)

        # now check the path cache!
        # there shouldbe two entries, one for the shot and one for the seq        
        pc = path_cache.PathCache(self.tk)
        shot_paths = pc.get_paths("Shot", self.shot["id"], primary_only=False)
        seq_paths = pc.get_paths("Sequence", self.seq["id"], primary_only=False)
        self.assertEqual(len(shot_paths), 1)
        self.assertEqual(len(seq_paths), 1)
        pc.close()
        
        # it's the same folder for seq and shot
        self.assertEqual(shot_paths, seq_paths)


    def test_task_a(self):
        """Tests paths used in making a shot are as expected."""

        folder.process_filesystem_structure(self.tk, 
                                            self.task["type"], 
                                            self.task ["id"], 
                                            preview=False,
                                            engine=None)        
        
        expected_paths = []

        shot_path = os.path.join(self.project_root, "%s_%s" % (self.shot["code"], self.seq["code"]))
        step_path = os.path.join(shot_path, "%s_%s" % (self.task["content"], self.step["short_name"]) )
        expected_paths.extend( [self.project_root, shot_path, step_path] )
        
        # add non-entity paths
        expected_paths.append(os.path.join(step_path, "images"))

        assert_paths_to_create(expected_paths)
                                
        # now check the path cache!
        # there should be two entries, one for the task and one for the step
        
        pc = path_cache.PathCache(self.tk)
        step_paths = pc.get_paths("Step", self.step["id"], primary_only=False)
        task_paths = pc.get_paths("Task", self.task["id"], primary_only=False)        
        self.assertEqual(len(step_paths), 1)
        self.assertEqual(len(task_paths), 1)
        # it's the same folder for seq and shot
        self.assertEqual(step_paths, task_paths)
        pc.close()

        
        # finally check the context.
        ctx = self.tk.context_from_path(step_path)
        self.assertEqual(ctx.task["id"], self.task["id"])
        self.assertEqual(ctx.task["type"], self.task["type"])
        # now because of the double entity matching, we should have a step and a task!
        self.assertEqual(ctx.step["id"], self.step["id"])
        self.assertEqual(ctx.step["type"], self.step["type"])
                                

