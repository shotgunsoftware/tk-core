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

from . import assert_paths_to_create, execute_folder_creation_proxy

# test against a step node where create_with_parent is false

class TestSchemaCreateFoldersSingleStep(TankTestBase):
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestSchemaCreateFoldersSingleStep, self).setUp()
        
        self.setup_fixtures("shotgun_single_step_core")
        
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
                     "project": self.project}

        self.task2 = {"type": "Task",
                     "id": 25,
                     "entity": self.shot,
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

        self.schema_location = os.path.join(self.project_root, "tank", "config", "core", "schema")

        self.FolderIOReceiverBackup = folder.folder_io.FolderIOReceiver.execute_folder_creation
        folder.folder_io.FolderIOReceiver.execute_folder_creation = execute_folder_creation_proxy

    def tearDown(self):
        
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


    def test_step_a(self):
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
        step_path = os.path.join(shot_path, self.step["short_name"])
        
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
        step_path = os.path.join(shot_path, self.step2["short_name"])
        
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
        
        self.setup_fixtures("shotgun_multi_step_core")
        
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
                     "project": self.project}

        self.task2 = {"type": "Task",
                     "id": 25,
                     "entity": self.shot,
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

        self.schema_location = os.path.join(self.project_root, "tank", "config", "core", "schema")

        self.FolderIOReceiverBackup = folder.folder_io.FolderIOReceiver.execute_folder_creation
        folder.folder_io.FolderIOReceiver.execute_folder_creation = execute_folder_creation_proxy

    def tearDown(self):
        
        folder.folder_io.FolderIOReceiver.execute_folder_creation = self.FolderIOReceiverBackup


    def make_path_list(self):
        
        expected_paths = []

        sequence_path = os.path.join(self.project_root, "sequences", self.seq["code"])        
        sequences_path = os.path.join(self.project_root, "sequences")
        shot_path = os.path.join(sequence_path, self.shot["code"])
        step_path = os.path.join(shot_path, self.step["short_name"])
        step2_path = os.path.join(shot_path, self.step2["short_name"])
        expected_paths.extend( [self.project_root, 
                                sequences_path, 
                                sequence_path, 
                                shot_path, 
                                step_path, 
                                step2_path] )
        
        # add non-entity paths
        for x in [step_path, step2_path]:
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
                                
                                



# make sure that user sandboxes can have step folders inside

class TestSchemaCreateFoldersStepAndUserSandbox(TankTestBase):
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestSchemaCreateFoldersStepAndUserSandbox, self).setUp()
        
        self.setup_fixtures("humanuser_step_core")
        
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
        
        self.task = {"type": "Task",
                     "id": 23,
                     "entity": self.shot,
                     "step": self.step,
                     "project": self.project}        

        cur_login = tank.util.login.get_login_name()
        
        self.humanuser = {"type": "HumanUser",
                          "id": 2,
                          "name": "Mr Current Login",
                          "login": cur_login}

        entities = [self.shot, 
                    self.task,
                    self.seq, 
                    self.step,
                    self.project,
                    self.humanuser]

        # Add these to mocked shotgun
        self.add_to_sg_mock_db(entities)

        

        self.schema_location = os.path.join(self.project_root, "tank", "config", "core", "schema")

        self.FolderIOReceiverBackup = folder.folder_io.FolderIOReceiver.execute_folder_creation
        folder.folder_io.FolderIOReceiver.execute_folder_creation = execute_folder_creation_proxy

    def tearDown(self):
        
        folder.folder_io.FolderIOReceiver.execute_folder_creation = self.FolderIOReceiverBackup


    @patch("tank.util.login.get_current_user")
    def test_shot(self, get_current_user):
        """Tests paths used in making a shot are as expected."""
        
        get_current_user.return_value = self.humanuser
        
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


    @patch("tank.util.login.get_current_user")
    def test_step_a(self, get_current_user):
        """Tests paths used in making a shot are as expected."""

        get_current_user.return_value = self.humanuser

        folder.process_filesystem_structure(self.tk, 
                                            self.task["type"], 
                                            self.task ["id"], 
                                            preview=False,
                                            engine="foo-bar")        
        
        expected_paths = []

        sequence_path = os.path.join(self.project_root, "sequences", self.seq["code"])   
        sequences_path = os.path.join(self.project_root, "sequences")     
        shot_path = os.path.join(sequence_path, self.shot["code"])
        sandbox_path = os.path.join(shot_path, self.humanuser["login"])
        step_path = os.path.join(sandbox_path, self.step["short_name"])
        
        expected_paths.extend( [self.project_root, sequences_path, sequence_path, shot_path, sandbox_path, step_path] )
        
        # add non-entity paths
        expected_paths.append(os.path.join(step_path, "publish"))
        expected_paths.append(os.path.join(step_path, "images"))
        expected_paths.append(os.path.join(step_path, "review"))
        expected_paths.append(os.path.join(step_path, "work"))
        expected_paths.append(os.path.join(step_path, "work", "snapshots"))
        expected_paths.append(os.path.join(step_path, "work", "workspace.mel"))
        expected_paths.append(os.path.join(step_path, "out"))

        assert_paths_to_create(expected_paths)
                                
                                
# test against a step node where create_with_parent is false
# and we are using a custom entity for step

class TestSchemaCreateFoldersCustomStep(TankTestBase):
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestSchemaCreateFoldersCustomStep, self).setUp()
        
        self.setup_fixtures("shotgun_single_custom_step_core")
        
        self.seq = {"type": "Sequence",
                    "id": 2,
                    "code": "seq_code",
                    "project": self.project}
        self.shot = {"type": "Shot",
                     "id": 1,
                     "code": "shot_code",
                     "sg_sequence": self.seq,
                     "project": self.project}
        self.step = {"type": "FooStep",
                     "id": 3,
                     "code": "step_code",
                     "short_name": "step_short_name"}

        self.step2 = {"type": "FooStep",
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
                     "step": None,
                     "alt_step_link": self.step,
                     "project": self.project}

        self.task2 = {"type": "Task",
                     "id": 25,
                     "entity": self.shot,
                     "step": None,
                     "alt_step_link": self.step2,
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

        self.schema_location = os.path.join(self.project_root, "tank", "config", "core", "schema")

        self.FolderIOReceiverBackup = folder.folder_io.FolderIOReceiver.execute_folder_creation
        folder.folder_io.FolderIOReceiver.execute_folder_creation = execute_folder_creation_proxy

    def tearDown(self):
        
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


    def test_step_a(self):
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
        step_path = os.path.join(shot_path, self.step["short_name"])
        
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
        step_path = os.path.join(shot_path, self.step2["short_name"])
        
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
                                
                                

