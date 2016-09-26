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
from tank import folder
from tank_test.tank_test_base import *

from . import assert_paths_to_create, execute_folder_creation_proxy

# test against a step node where create_with_parent is false

class TestSchemaCreateFoldersSingleStep(TankTestBase):
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestSchemaCreateFoldersSingleStep, self).setUp()
        
        self.setup_fixtures(parameters = {"core": "core.override/shotgun_single_task_core"})
        
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
                     "content": "task1",
                     "project": self.project}

        self.task2 = {"type": "Task",
                     "id": 25,
                     "entity": self.shot,
                     "step": self.step2,
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
        super(TestSchemaCreateFoldersSingleStep, self).tearDown()
        
        # and do local teardown                                                                                
        folder.folder_io.FolderIOReceiver.execute_folder_creation = self.FolderIOReceiverBackup


    def test_shot(self):
        """Tests paths used in making a shot are as expected."""
        
        expected_paths = []
        
        sequence_path = os.path.join(self.project_root, "sequences", self.seq["code"])
        sequences_path = os.path.join(self.project_root, "sequences")
        shot_path = os.path.join(sequence_path, self.shot["code"])

        expected_paths.extend( [self.project_root, sequences_path, sequence_path, shot_path] )

        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine=None)        
        
        assert_paths_to_create(expected_paths)


    def test_task_a(self):
        """Tests paths used in making a shot are as expected."""

        folder.process_filesystem_structure(self.tk, 
                                            self.task["type"], 
                                            self.task ["id"], 
                                            preview=False,
                                            engine=None)        
        
        expected_paths = []

        sequence_path = os.path.join(self.project_root, "sequences", self.seq["code"])
        sequences_path = os.path.join(self.project_root, "sequences")        
        shot_path = os.path.join(sequence_path, self.shot["code"])
        step_path = os.path.join(shot_path, self.task["content"])
        
        expected_paths.extend( [self.project_root, sequences_path, sequence_path, shot_path, step_path] )
        
        # add non-entity paths
        expected_paths.append(os.path.join(step_path, "publish"))
        expected_paths.append(os.path.join(step_path, "images"))
        expected_paths.append(os.path.join(step_path, "review"))
        expected_paths.append(os.path.join(step_path, "work"))
        expected_paths.append(os.path.join(step_path, "work", "snapshots"))
        expected_paths.append(os.path.join(step_path, "work", "workspace.mel"))
        expected_paths.append(os.path.join(step_path, "out"))

        assert_paths_to_create(expected_paths)
                                
                                
    def test_step_b(self):
        """Tests paths used in making a shot are as expected."""

        folder.process_filesystem_structure(self.tk, 
                                            self.task2["type"], 
                                            self.task2["id"], 
                                            preview=False,
                                            engine=None)        
        
        expected_paths = []

        sequence_path = os.path.join(self.project_root, "sequences", self.seq["code"])   
        sequences_path = os.path.join(self.project_root, "sequences")     
        shot_path = os.path.join(sequence_path, self.shot["code"])
        step_path = os.path.join(shot_path, self.task2["content"])
        
        expected_paths.extend( [self.project_root, sequences_path, sequence_path, shot_path, step_path] )
        
        # add non-entity paths
        expected_paths.append(os.path.join(step_path, "publish"))
        expected_paths.append(os.path.join(step_path, "images"))
        expected_paths.append(os.path.join(step_path, "review"))
        expected_paths.append(os.path.join(step_path, "work"))
        expected_paths.append(os.path.join(step_path, "work", "snapshots"))
        expected_paths.append(os.path.join(step_path, "work", "workspace.mel"))
        expected_paths.append(os.path.join(step_path, "out"))

        assert_paths_to_create(expected_paths)
                                
                                




# test against a step node where create_with_parent is true

class TestSchemaCreateFoldersMultiStep(TankTestBase):
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestSchemaCreateFoldersMultiStep, self).setUp()
        
        self.setup_fixtures(parameters = {"core": "core.override/shotgun_multi_task_core"})
                
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
                     "content": "task1",
                     "step": self.step,
                     "project": self.project}

        self.task2 = {"type": "Task",
                     "id": 25,
                     "entity": self.shot,
                     "content": "task2",
                     "step": self.step2,
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
        super(TestSchemaCreateFoldersMultiStep, self).tearDown()
        
        # and do local teardown                                                                                        
        folder.folder_io.FolderIOReceiver.execute_folder_creation = self.FolderIOReceiverBackup


    def make_path_list(self):
        
        expected_paths = []

        sequence_path = os.path.join(self.project_root, "sequences", self.seq["code"])
        sequences_path = os.path.join(self.project_root, "sequences")
        shot_path = os.path.join(sequence_path, self.shot["code"])
        task_path = os.path.join(shot_path, self.task["content"])
        task2_path = os.path.join(shot_path, self.task2["content"])
        
        expected_paths.extend( [self.project_root, 
                                sequences_path, 
                                sequence_path, 
                                shot_path, 
                                task_path, 
                                task2_path] )
        
        # add non-entity paths
        for x in [task_path, task2_path]:
            expected_paths.append(os.path.join(x, "publish"))
            expected_paths.append(os.path.join(x, "images"))
            expected_paths.append(os.path.join(x, "review"))
            expected_paths.append(os.path.join(x, "work"))
            expected_paths.append(os.path.join(x, "work", "snapshots"))
            expected_paths.append(os.path.join(x, "work", "workspace.mel"))
            expected_paths.append(os.path.join(x, "out"))
        
        return expected_paths


    def test_shot(self):
        """Tests paths used in making a shot are as expected."""
        
        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine=None)        
        
        assert_paths_to_create(self.make_path_list())


    def test_step_a(self):
        """Tests paths used in making a shot are as expected."""

        folder.process_filesystem_structure(self.tk, 
                                            self.task["type"], 
                                            self.task ["id"], 
                                            preview=False,
                                            engine=None)        
        

        assert_paths_to_create(self.make_path_list())
                                

    def test_step_b(self):
        """Tests paths used in making a shot are as expected."""

        folder.process_filesystem_structure(self.tk, 
                                            self.task2["type"], 
                                            self.task2["id"], 
                                            preview=False,
                                            engine=None)        
        
        assert_paths_to_create(self.make_path_list())
                                
                                
    def test_context_from_path(self):
        """Testing task based context resolution from path."""

        task_path = os.path.join(
            self.project_root,
            "sequences",
            self.seq["code"],
            self.shot["code"],
            self.task["content"]
        )

        # before folders exist for the task, we expect
        # only the project to be extracted from the path
        ctx = self.tk.context_from_path(task_path)

        self.assertEqual(ctx.project, {'type': 'Project', 'id': 1, 'name': 'project_name'})
        self.assertEqual(ctx.entity, None)
        self.assertEqual(ctx.step, None)
        self.assertEqual(ctx.task, None)

        # create folders
        folder.process_filesystem_structure(self.tk,
                                            self.task["type"],
                                            self.task ["id"],
                                            preview=False,
                                            engine=None)


        # now we should get a full context, including step
        ctx = self.tk.context_from_path(task_path)

        self.assertEqual(ctx.project, {'type': 'Project', 'id': 1, 'name': 'project_name'})
        self.assertEqual(ctx.entity, {'type': 'Shot', 'id': 1, 'name': 'shot_code'})
        self.assertEqual(ctx.step, {'type': 'Step', 'id': 3, 'name': 'step_code'})
        self.assertEqual(ctx.task, {'type': 'Task', 'id': 23, 'name': 'task1'})

