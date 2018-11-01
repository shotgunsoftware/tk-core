# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import copy
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

class TestSchemaCreateFolders(TankTestBase):
    
    def setUp(self, project_tank_name = "project_code"):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestSchemaCreateFolders, self).setUp(parameters = {"project_tank_name": project_tank_name })
        self.setup_fixtures()
        
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
                     "entity_type": "Shot",
                     "short_name": "step_short_name"}
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

        entities = [self.shot, self.seq, self.step, self.project, self.asset, self.task]

        # Add these to mocked shotgun
        self.add_to_sg_mock_db(entities)

        self.schema_location = os.path.join(self.pipeline_config_root, "config", "core", "schema")

        self.FolderIOReceiverBackup = folder.folder_io.FolderIOReceiver.execute_folder_creation
        folder.folder_io.FolderIOReceiver.execute_folder_creation = execute_folder_creation_proxy

    def tearDown(self):
        
        # important to call base class so it can clean up memory
        super(TestSchemaCreateFolders, self).tearDown()
        
        # and do local teardown
        folder.folder_io.FolderIOReceiver.execute_folder_creation = self.FolderIOReceiverBackup


    def test_shot(self):
        """Tests paths used in making a shot are as expected."""
        expected_paths = self._construct_shot_paths()
        
        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine=None)        
        assert_paths_to_create(expected_paths)

    def test_white_space(self):
        # make illegal value
        self.shot["code"] = "name with spaces"
        
        expected_paths = self._construct_shot_paths(shot_name="name-with-spaces")

        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine=None)        
        
        assert_paths_to_create(expected_paths)

    def test_unicode(self):
        # make illegal value
        
        # some japanese characters, UTF-8 encoded, just like we would get the from
        # the shotgun API.
        
        self.shot["code"] = "\xe3\x81\xbe\xe3\x82\x93\xe3\x81\x88 foo bar"
        
        expected_paths = self._construct_shot_paths(shot_name="\xe3\x81\xbe\xe3\x82\x93\xe3\x81\x88-foo-bar")

        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine=None)        
        
        assert_paths_to_create(expected_paths)

    def test_illegal_chars(self):
        illegal_chars = ["~", "!", "@", "#", "$", "%", "^", "&", "*", "(", ")",
                         "+", "=", ":", ";", "'", "\"", "<", ">", "/", "?", 
                         "|", "/", "\\"]
        for illegal_char in illegal_chars:
            self.shot["code"] = "shot%sname" % illegal_char
            self.add_to_sg_mock_db(self.shot)
            expected_paths = self._construct_shot_paths(shot_name="shot-name")

            folder.process_filesystem_structure(self.tk, 
                                                self.shot["type"], 
                                                self.shot["id"], 
                                                preview=False,
                                                engine=None)        
            
            assert_paths_to_create(expected_paths)

    def test_asset(self):
        """Tests paths used in making a asset are as expected."""
        # expected paths here are based on sg_standard start-config
        # define paths we expect for entities
        
        static_assets = os.path.join(self.project_root, "assets")
        asset_type_path = os.path.join(static_assets, self.asset["sg_asset_type"])
        asset_path = os.path.join(asset_type_path, self.asset["code"])        
        step_path = os.path.join(asset_path, self.step["short_name"])
        
        expected_paths = [self.project_root,
                          os.path.join(self.project_root, "reference"),
                          os.path.join(self.project_root, "scenes"),
                          os.path.join(self.project_root, "sequences"),
                          os.path.join(self.project_root, "reference", "artwork"),
                          os.path.join(self.project_root, "reference", "footage"),
                          static_assets,
                          asset_type_path, 
                          asset_path, 
                          step_path]
        
        # add non-entity paths
        expected_paths.append(os.path.join(step_path, "publish"))
        expected_paths.append(os.path.join(step_path, "images"))
        expected_paths.append(os.path.join(step_path, "review"))
        expected_paths.append(os.path.join(step_path, "work"))
        expected_paths.append(os.path.join(step_path, "work", "snapshots"))
        expected_paths.append(os.path.join(step_path, "out"))

        folder.process_filesystem_structure(self.tk, 
                                            self.asset["type"], 
                                            self.asset["id"], 
                                            preview=False,
                                            engine=None)        
        
        assert_paths_to_create(expected_paths)
    
    def test_scene(self):
        """Tests folder creation works with Step higher up the hierarchy than normal"""
        
        scene = {
            "type": "Scene",
            "id": 5,
            "code": "scenename",
            "project": self.project
        }
        
        extra_step = {
            "type": "Step",
            "id": 6,
            "entity_type": "Scene",
            "code": "scene_step_code",
            "short_name": "scene_step_name"
        }
        
        self.add_to_sg_mock_db([scene, extra_step])
        
        expected_paths = [self.project_root,
                          os.path.join(self.project_root, "reference"),
                          os.path.join(self.project_root, "sequences"),
                          os.path.join(self.project_root, "assets"),
                          os.path.join(self.project_root, "reference", "artwork"),
                          os.path.join(self.project_root, "reference", "footage"),                          
                          ]
                
                              
        expected_paths.append(os.path.join(self.project_root, "scenes"))
        expected_paths.append(os.path.join(self.project_root, "scenes", "scene_step_name"))
        expected_paths.append(os.path.join(self.project_root, "scenes", "scene_step_name", "scenename"))
        expected_paths.append(os.path.join(self.project_root, "scenes", "scene_step_name", "scenename", "work"))
        
        folder.process_filesystem_structure(self.tk, 
                                            scene["type"], 
                                            scene["id"], 
                                            preview=False,
                                            engine=None)        
        
        assert_paths_to_create(expected_paths)

    def test_project(self):
        """Tests paths used in making a project are as expected."""
                
        # paths based on sg_standard starter config
        expected_paths = []
        expected_paths.append(self.project_root)
        expected_paths.append(os.path.join(self.project_root, "sequences"))
        expected_paths.append(os.path.join(self.project_root, "scenes"))
        expected_paths.append(os.path.join(self.project_root, "assets"))
        expected_paths.append(os.path.join(self.project_root, "reference"))
        expected_paths.append(os.path.join(self.project_root, "reference", "artwork"))
        expected_paths.append(os.path.join(self.project_root, "reference", "footage"))

        folder.process_filesystem_structure(self.tk, 
                                            self.project["type"], 
                                            self.project["id"],  
                                            preview=False,
                                            engine=None)        
        
        assert_paths_to_create(expected_paths)

    def _construct_shot_paths(self, sequence_name=None, shot_name=None, step_name=None):
        """
        Constructs expected paths for a shot based on the sg_standard standard config.

        :param sequence_name: Override for the name of the sequence directory.
        :param shot_name: Override for the name of the shot directory.
        :param step_name: Override for the name of the step directory.

        :returns: List of paths
        """
        # expected paths here are based on sg_standard start-config
        # define paths we expect for entities
        if not sequence_name:
            sequence_name = self.seq["code"]

        static_seq = os.path.join(self.project_root, "sequences")        

        expected_paths = [self.project_root, 
                          os.path.join(self.project_root, "reference"),
                          os.path.join(self.project_root, "scenes"),
                          os.path.join(self.project_root, "assets"),
                          os.path.join(self.project_root, "reference", "artwork"),
                          os.path.join(self.project_root, "reference", "footage"),                          
                          static_seq]

        sequence_path = os.path.join(self.project_root, "sequences", sequence_name)
        if not shot_name:
            shot_name = self.shot["code"]
        shot_path = os.path.join(sequence_path, shot_name)

        step_path = os.path.join(shot_path, self.step["short_name"])
        expected_paths.extend( [sequence_path, shot_path, step_path] )
        # add non-entity paths
        expected_paths.append(os.path.join(step_path, "publish"))
        expected_paths.append(os.path.join(step_path, "images"))
        expected_paths.append(os.path.join(step_path, "review"))
        expected_paths.append(os.path.join(step_path, "work"))
        expected_paths.append(os.path.join(step_path, "work", "snapshots"))
        expected_paths.append(os.path.join(step_path, "work", "workspace.mel"))
        expected_paths.append(os.path.join(step_path, "out"))
        
        return expected_paths







class TestSchemaCreateFoldersMultiLevelProjectRoot(TestSchemaCreateFolders):

    """ 
    Test a setup where there are more than a single folder in the Project.tank_name.
    
    We just run the standard tests but with an extended project root path. 
    """

    def setUp(self):        
        super(TestSchemaCreateFoldersMultiLevelProjectRoot, self).setUp(project_tank_name="multi/root/project/name")

        




                                
                                
class TestSchemaCreateFoldersMultiRoot(TankTestBase):
    """Test paths generated by Schema.create folders for multi-root project."""
    
    
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestSchemaCreateFoldersMultiRoot, self).setUp()
        
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

        

        self.FolderIOReceiverBackup = folder.folder_io.FolderIOReceiver.execute_folder_creation
        folder.folder_io.FolderIOReceiver.execute_folder_creation = execute_folder_creation_proxy

    def tearDown(self):
        
        # important to call base class so it can clean up memory
        super(TestSchemaCreateFoldersMultiRoot, self).tearDown()
        
        # and do local teardown        
        folder.folder_io.FolderIOReceiver.execute_folder_creation = self.FolderIOReceiverBackup
        

    def test_shot(self):
        """Tests paths used in making a shot are as expected."""
        expected_paths = self._construct_shot_paths()
        
        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine=None)        
        
        assert_paths_to_create(expected_paths)
        

    def test_asset(self):
        """Tests paths used in making a asset are as expected."""
        # expected paths here are based on sg_standard start-config
        # define paths we expect for entities
        
        expected_paths = []
        
        expected_paths.append(self.alt_root_1)
        expected_paths.append(os.path.join(self.alt_root_1, "assets"))
        expected_paths.append(os.path.join(self.alt_root_1, "alternate_reference"))        
        
        asset_folder_name = "%s_%s" % (self.asset["sg_asset_type"], self.asset["code"])
        asset_path = os.path.join(self.alt_root_1, "assets", asset_folder_name)
        step_path = os.path.join(asset_path, self.step["short_name"])
        expected_paths.append(asset_path)
        expected_paths.append(step_path)
        
        # add non-entity paths
        expected_paths.append(os.path.join(step_path, "publish"))
        expected_paths.append(os.path.join(step_path, "images"))
        expected_paths.append(os.path.join(step_path, "review"))
        expected_paths.append(os.path.join(step_path, "work"))
        expected_paths.append(os.path.join(step_path, "work", "snapshots"))
        expected_paths.append(os.path.join(step_path, "out"))

        folder.process_filesystem_structure(self.tk, 
                                            self.asset["type"], 
                                            self.asset["id"], 
                                            preview=False,
                                            engine=None)        

        assert_paths_to_create(expected_paths)

    def test_project(self):
        """
        Tests paths used in making a project are as expected when single project directory
        with no yaml file exits.
        """
        # paths based on sg_standard starter config modified to be multi-project
        expected_paths = []
        expected_paths.append(self.project_root)
        expected_paths.append(os.path.join(self.project_root, "sequences"))
        expected_paths.append(os.path.join(self.project_root, "reference"))
        expected_paths.append(os.path.join(self.project_root, "reference", "artwork"))
        expected_paths.append(os.path.join(self.project_root, "reference", "footage"))

        expected_paths.append(self.alt_root_1)
        expected_paths.append(os.path.join(self.alt_root_1, "assets"))
        expected_paths.append(os.path.join(self.alt_root_1, "alternate_reference"))
                
        folder.process_filesystem_structure(self.tk, 
                                            self.project["type"], 
                                            self.project["id"], 
                                            preview=False,
                                            engine=None)        
        
        assert_paths_to_create(expected_paths)

    def _construct_shot_paths(self, sequence_name=None, shot_name=None, step_name=None):
        """
        Constructs expected paths for a shot based on the multi root test schema

        :param sequence_name: Override for the name of the sequence directory.
        :param shot_name: Override for the name of the shot directory.
        :param step_name: Override for the name of the step directory.

        :returns: List of paths
        """
        
        expected_paths = []
        expected_paths.append(self.project_root)
        expected_paths.append(os.path.join(self.project_root, "sequences"))
        expected_paths.append(os.path.join(self.project_root, "reference"))
        expected_paths.append(os.path.join(self.project_root, "reference", "artwork"))
        expected_paths.append(os.path.join(self.project_root, "reference", "footage"))
        
        # expected paths here are based on sg_standard start-config
        # define paths we expect for entities
        if not sequence_name:
            sequence_name = self.seq["code"]

        sequence_path = os.path.join(self.project_root, "sequences", sequence_name)
        if not shot_name:
            shot_name = self.shot["code"]
        shot_path = os.path.join(sequence_path, shot_name)

        step_path = os.path.join(shot_path, self.step["short_name"])
        expected_paths.extend( [sequence_path, shot_path, step_path] )
        # add non-entity paths
        expected_paths.append(os.path.join(step_path, "publish"))
        expected_paths.append(os.path.join(step_path, "images"))
        expected_paths.append(os.path.join(step_path, "review"))
        expected_paths.append(os.path.join(step_path, "work"))
        expected_paths.append(os.path.join(step_path, "work", "snapshots"))
        expected_paths.append(os.path.join(step_path, "out"))
        return expected_paths


class TestCreateFilesystemStructure(TankTestBase):
    """Tests of the function schema.create_folders."""
    def setUp(self):
        super(TestCreateFilesystemStructure, self).setUp()
        self.setup_fixtures()
        
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
        self.task = {"type":"Task",
                     "id": 1,
                     "content": "this task",
                     "entity": self.shot,
                     "step": {"type": "Step", "id": 3},
                     "project": self.project}

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.shot, self.seq, self.step, self.project, self.asset, self.task])
        

    def test_create_task(self):
        # Task should create folders for it's entity
        expected = os.path.join(self.project_root, "sequences", self.seq["code"], self.shot["code"])
        self.assertFalse(os.path.exists(expected))
        folder.process_filesystem_structure(self.tk, 
                                            self.task["type"], 
                                            self.task["id"], 
                                            preview=False, 
                                            engine=None)
        self.assertTrue(os.path.exists(expected))

    def test_create_shot(self):
        expected = os.path.join(self.project_root, "sequences", self.seq["code"], self.shot["code"])
        self.assertFalse(os.path.exists(expected))
        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine=None)        
        self.assertTrue(os.path.exists(expected))

    def test_create_asset(self):
        expected = os.path.join(self.project_root, "assets", self.asset["sg_asset_type"], self.asset["code"])
        self.assertFalse(os.path.exists(expected))
        folder.process_filesystem_structure(self.tk, 
                                            self.asset["type"], 
                                            self.asset["id"], 
                                            preview=False,
                                            engine=None)
        self.assertTrue(os.path.exists(expected))

    def test_create_project(self):
        # Check static folders without entity children are created
        expected = os.path.join(self.project_root, "reference", "artwork")
        self.assertFalse(os.path.exists(expected))
        folder.process_filesystem_structure(self.tk, 
                                            self.project["type"], 
                                            self.project["id"], 
                                            preview=False,
                                            engine=None)
        self.assertTrue(os.path.exists(expected))

    def test_create_sequence(self):
        expected = os.path.join(self.project_root, "sequences", self.seq["code"])
        self.assertFalse(os.path.exists(expected))
        folder.process_filesystem_structure(self.tk, 
                                            self.seq["type"], 
                                            self.seq["id"], 
                                            preview=False,
                                            engine=None)
        self.assertTrue(os.path.exists(expected))

              
    def test_wrong_type_entity_ids(self):
        """Test passing in type other than list, int or tuple as value for entity_ids parameter.
        """
        for bad_entity_ids in ["abab", self.shot, object()]:
            self.assertRaises(ValueError, 
                              folder.process_filesystem_structure, 
                              self.tk,
                              self.shot["type"],
                              bad_entity_ids,
                              preview=False,
                              engine=None)
              
              
     



class TestSchemaCreateFoldersWorkspaces(TankTestBase):
    """
    This test
    covers the case where you have an entity (for example a workspace
    entity) which has a sg_entity single link field which can point to both
    assets and shots. If you run folder creation on this, the algorithm
    should be able to correctly distinguish between items linked to shots
    and items linked to assets.    
    """
    
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestSchemaCreateFoldersWorkspaces, self).setUp()
        
        self.setup_fixtures(parameters = {"core": "core.override/multi_link_core"})
        
        self.seq = {"type": "Sequence",
                    "id": 2,
                    "code": "seq_code",
                    "project": self.project}
        
        self.shot = {"type": "Shot",
                     "id": 1,
                     "code": "shot_code",
                     "sg_sequence": self.seq,
                     "project": self.project}
        
        self.workspace = {"type": "CustomEntity02",
                     "id": 3,
                     "sg_entity": self.shot,
                     "project": self.project,
                     "code": "workspace_code_shot"}

        
        self.asset = {"type": "Asset",
                    "id": 4,
                    "sg_asset_type": "assettype",
                    "code": "assetname",
                    "project": self.project}

        self.workspace2 = {"type": "CustomEntity02",
                     "id": 5,
                     "sg_entity": self.asset,
                     "project": self.project,
                     "code": "workspace_code_asset"}

        # need to register the sg_entity link we just made up with the mocker
        field_def = {'data_type': {'editable': False, 'value': 'entity'},
                     'description': {'editable': True, 'value': ''},
                     'editable': {'editable': False, 'value': True},
                     'entity_type': {'editable': False, 'value': 'CustomEntity02'},
                     'mandatory': {'editable': False, 'value': False},
                     'name': {'editable': True, 'value': 'Entity'},
                     'properties': {'default_value': {'editable': False, 'value': None},
                     'summary_default': {'editable': True, 'value': 'none'},
                     'valid_types': {'editable': True, 'value': ['Shot', 'Asset']}},
                     'unique': {'editable': False, 'value': False}}
        
        # FIXME: The schema is cached in memory for unit tests to reuse, modifying this is BAD.
        self.tk.shotgun._schema = copy.deepcopy(self.tk.shotgun._schema)
        self.tk.shotgun._schema["CustomEntity02"]["sg_entity"] = field_def


        entities = [self.shot, 
                    self.seq, 
                    self.project, 
                    self.asset, 
                    self.workspace,
                    self.workspace2]

        # Add these to mocked shotgun
        self.add_to_sg_mock_db(entities)

        self.schema_location = os.path.join(self.pipeline_config_root, "config", "core", "schema")

        self.FolderIOReceiverBackup = folder.folder_io.FolderIOReceiver.execute_folder_creation
        folder.folder_io.FolderIOReceiver.execute_folder_creation = execute_folder_creation_proxy

    def tearDown(self):
        
        # important to call base class so it can clean up memory
        super(TestSchemaCreateFoldersWorkspaces, self).tearDown()
        
        # and do local teardown                
        folder.folder_io.FolderIOReceiver.execute_folder_creation = self.FolderIOReceiverBackup


    def test_shot(self):
        """Tests paths used in making a shot are as expected."""
        
        
        sequence_path = os.path.join(self.project_root, "sequences", self.seq["code"])
        sequences_path = os.path.join(self.project_root, "sequences")        
        shot_path = os.path.join(sequence_path, self.shot["code"])
        ws_path = os.path.join(shot_path, self.workspace["code"])

        expected_paths = [self.project_root,                          
                          os.path.join(self.project_root, "assets"),
                          ]
        
        
        expected_paths.extend( [sequences_path, 
                                sequence_path, 
                                shot_path,
                                ws_path] )

        folder.process_filesystem_structure(self.tk, 
                                            self.workspace["type"], 
                                            self.workspace["id"], 
                                            preview=False,
                                            engine=None)        
        
        assert_paths_to_create(expected_paths)


    def test_asset(self):
        """Tests paths used in making a shot are as expected."""
        
        
        assets_path = os.path.join(self.project_root, "assets")
        at_path = os.path.join(assets_path, "assettype")
        asset_path = os.path.join(at_path, self.asset["code"])
        ws_path = os.path.join(asset_path, self.workspace2["code"])

        expected_paths = []
        expected_paths.extend( [self.project_root, 
                                os.path.join(self.project_root, "sequences"),
                                assets_path, 
                                at_path, 
                                asset_path,
                                ws_path] )

        folder.process_filesystem_structure(self.tk, 
                                            self.workspace2["type"], 
                                            self.workspace2["id"], 
                                            preview=False,
                                            engine=None)        
        
        assert_paths_to_create(expected_paths)







class TestFolderCreationEdgeCases(TankTestBase):
    """
    Tests renaming edge cases etc.
    
    """
    def setUp(self):
        super(TestFolderCreationEdgeCases, self).setUp()
        
        self.setup_fixtures()
        
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
        self.task = {"type":"Task",
                     "id": 1,
                     "content": "this task",
                     "entity": self.shot,
                     "step": {"type": "Step", "id": 3},
                     "project": self.project}

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.shot, self.seq, self.step, self.project, self.task])
        
        self.path_cache = path_cache.PathCache(self.tk)

    def tearDown(self):

        # and do local teardown                        
        # making sure that no file handles remain active 
        # leftover handles cause problems on windows! 
        self.path_cache.close()
        self.path_cache = None
        
        # important to call base class so it can clean up memory
        super(TestFolderCreationEdgeCases, self).tearDown()
        



    def test_delete_shot_then_recreate(self):
        
        # 1. create fodlers for shot ABC
        # 2. delete shot ABC from SG
        # 3. create a new shot ABC in SG
        # 4. when creating folders, it should delete the previous records and replace with new
        
        self.assertEqual(self.path_cache.get_paths("Shot", self.shot["id"], False), [])
        
        folder.process_filesystem_structure(self.tk, 
                                            self.task["type"], 
                                            self.task["id"], 
                                            preview=False, 
                                            engine=None)
        
        # check that it is in the db
        shot_path = os.path.join(self.project_root, "sequences", "seq_code", "shot_code")
        paths_in_db = self.path_cache.get_paths("Shot", self.shot["id"], False)
        self.assertEqual(paths_in_db, [shot_path])
        
        # change the id of the shot - effectively deleting and creating a shot!
        old_id = self.shot["id"]
        self.shot["id"] = 12345
        # make sure to null the link going from the task too - this is how shotgun
        # would have done a retirement.
        self.task["entity"] = self.shot
        
        self.assertEqual(self.path_cache.get_paths("Shot", self.shot["id"], False), [])
        
        self.assertRaisesRegex(TankError, 
                                "Folder creation aborted.*unregister_folders",
                                folder.process_filesystem_structure,
                                self.tk,
                                self.task["type"],
                                self.task["id"], 
                                preview=False, 
                                engine=None)
        
        # Folder creation aborted: The path '.../project_code/sequences/seq_code/shot_code' cannot be processed 
        # because it is already associated with Shot 'shot_code' (id 1) in Shotgun. You are now trying to 
        # associate it with Shot 'shot_code' (id 12345). If you want to unregister your previously created 
        # folders, you can run the following command: 'tank Shot shot_code unregister_folders'         
        
        
        
        
        
        
        

    def test_rename_shot_but_keep_on_disk(self):
        
        # 1. create fodlers for shot ABC
        # 2. rename shot to XYZ
        # 3. create folders --> ERROR
        

        folder.process_filesystem_structure(self.tk, 
                                            self.task["type"], 
                                            self.task["id"], 
                                            preview=False, 
                                            engine=None)
        
        # rename the shot
        self.shot["code"] = "XYZ"

        self.assertRaisesRegex(TankError, 
                                "Folder creation aborted.*unregister_folders",
                                folder.process_filesystem_structure,
                                self.tk,
                                self.task["type"],
                                self.task["id"], 
                                preview=False, 
                                engine=None)

        # Folder creation aborted: The path '.../project_code/sequences/seq_code/shot_code' cannot be processed 
        # because it is already associated with Shot 'shot_code' (id 1) in Shotgun. You are now trying to 
        # associate it with Shot 'shot_code' (id 12345). If you want to unregister your previously created 
        # folders, you can run the following command: 'tank Shot shot_code unregister_folders'         


        # Previously, if I deleted the old folder on disk, the folder creation should have proceeded
        # now, it just gives the same error message
        shot_path = os.path.join(self.project_root, "sequences", "seq_code", "shot_code")
        renamed_shot_path = os.path.join(self.project_root, "sequences", "seq_code", "shot_code_renamed")
        shutil.move(shot_path, renamed_shot_path)

        self.assertRaisesRegex(TankError, 
                                "Folder creation aborted.*unregister_folders",
                                folder.process_filesystem_structure,
                                self.tk,
                                self.task["type"],
                                self.task["id"], 
                                preview=False, 
                                engine=None)

        
              
     

