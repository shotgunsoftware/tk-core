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
from tank import path_cache
from tank import folder
from tank_test.tank_test_base import *


def assert_paths_to_create(expected_paths):
    """
    No file system operations are performed.
    """
    # Check paths sent to make_folder
    for expected_path in expected_paths:
        if expected_path not in g_paths_created:
            assert False, "\n%s\nnot found in: [\n%s]" % (expected_path, "\n".join(g_paths_created))
    for actual_path in g_paths_created:
        if actual_path not in expected_paths:
            assert False, "Unexpected path slated for creation: %s \nPaths: %s" % (actual_path, "\n".join(g_paths_created))


g_paths_created = []

def execute_folder_creation_proxy(self):
    """
    Proxy stub for folder creation tests
    """
        
    # now handle the path cache
    if not self._preview_mode: 
        for i in self._items:
            if i.get("action") == "entity_folder":
                path = i.get("path")
                entity_type = i.get("entity").get("type")
                entity_id = i.get("entity").get("id")
                entity_name = i.get("entity").get("name")
                self._path_cache.add_mapping(entity_type, entity_id, entity_name, path)
        for i in self._secondary_cache_entries:
            path = i.get("path")
            entity_type = i.get("entity").get("type")
            entity_id = i.get("entity").get("id")
            entity_name = i.get("entity").get("name")
            self._path_cache.add_mapping(entity_type, entity_id, entity_name, path, False)
        

    # finally, build a list of all paths calculated
    folders = list()
    for i in self._items:
        action = i.get("action")
        if action in ["entity_folder", "create_file", "folder"]:
            folders.append( i["path"] )
        elif action == "copy":
            folders.append( i["target_path"] )
    
    global g_paths_created
    g_paths_created = folders
    
    return folders






class TestSchemaCreateFolders(TankTestBase):
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestSchemaCreateFolders, self).setUp()
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
        self.task = {"type": "Task",
                     "id": 23,
                     "entity": self.shot,
                     "step": self.step,
                     "project": self.project}

        entities = [self.shot, self.seq, self.step, self.project, self.asset, self.task]

        # Add these to mocked shotgun
        self.add_to_sg_mock_db(entities)

        self.tk = tank.Tank(self.project_root)

        # add mock schema data so that a list of the asset type enum values can be returned
        data = {}
        data["properties"] = {}
        data["properties"]["valid_values"] = {}
        data["properties"]["valid_values"]["value"] = ["assettype"]
        data["data_type"] = {}
        data["data_type"]["value"] = "list"        
        self.add_to_sg_schema_db("Asset", "sg_asset_type", data)

        self.schema_location = os.path.join(self.project_root, "tank", "config", "core", "schema")

        self.FolderIOReceiverBackup = folder.folder_io.FolderIOReceiver.execute_folder_creation
        folder.folder_io.FolderIOReceiver.execute_folder_creation = execute_folder_creation_proxy

    def tearDown(self):
        
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

        self.tk = tank.Tank(self.project_root)

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
            "code": "step_code",
            "short_name": "extra_short_name"
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
        expected_paths.append(os.path.join(self.project_root, "scenes", "step_short_name"))
        expected_paths.append(os.path.join(self.project_root, "scenes", "step_short_name", "scenename"))
        expected_paths.append(os.path.join(self.project_root, "scenes", "step_short_name", "scenename", "work"))
        expected_paths.append(os.path.join(self.project_root, "scenes", "extra_short_name"))
        expected_paths.append(os.path.join(self.project_root, "scenes", "extra_short_name", "scenename"))
        expected_paths.append(os.path.join(self.project_root, "scenes", "extra_short_name", "scenename", "work"))
        
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

        self.tk = tank.Tank(self.project_root)

        self.FolderIOReceiverBackup = folder.folder_io.FolderIOReceiver.execute_folder_creation
        folder.folder_io.FolderIOReceiver.execute_folder_creation = execute_folder_creation_proxy

    def tearDown(self):
        
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
        expected_paths.append(os.path.join(self.alt_root_1, "tank", "config", "primary_project.yml"))
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
        expected_paths.append(os.path.join(self.alt_root_1, "tank", "config", "primary_project.yml"))
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
        
        self.tk = tank.Tank(self.project_root)
        
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
        
        self.tk = tank.Tank(self.project_root)
        
        # add mock schema data so that a list of the asset type enum values can be returned
        data = {}
        data["properties"] = {}
        data["properties"]["valid_values"] = {}
        data["properties"]["valid_values"]["value"] = ["assettype"]
        data["data_type"] = {}
        data["data_type"]["value"] = "list"
        self.add_to_sg_schema_db("Asset", "sg_asset_type", data)


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
        self.setup_fixtures("multi_link_core")
        
        self.seq = {"type": "Sequence",
                    "id": 2,
                    "code": "seq_code",
                    "project": self.project}
        self.shot = {"type": "Shot",
                     "id": 1,
                     "code": "shot_code",
                     "sg_sequence": self.seq,
                     "project": self.project}
        self.workspace = {"type": "Workspace",
                     "id": 3,
                     "sg_entity": self.shot,
                     "code": "workspace_code_shot"}

        
        self.asset = {"type": "Asset",
                    "id": 4,
                    "sg_asset_type": "assettype",
                    "code": "assetname",
                    "project": self.project}

        self.workspace2 = {"type": "Workspace",
                     "id": 5,
                     "sg_entity": self.asset,
                     "code": "workspace_code_asset"}


        entities = [self.shot, 
                    self.seq, 
                    self.project, 
                    self.asset, 
                    self.workspace,
                    self.workspace2]

        # Add these to mocked shotgun
        self.add_to_sg_mock_db(entities)

        self.tk = tank.Tank(self.project_root)

        # add mock schema data so that a list of the asset type enum values can be returned
        data = {}
        data["properties"] = {}
        data["properties"]["valid_values"] = {}
        data["properties"]["valid_values"]["value"] = ["assettype"]
        data["data_type"] = {}
        data["data_type"]["value"] = "list"        
        self.add_to_sg_schema_db("Asset", "sg_asset_type", data)

        self.schema_location = os.path.join(self.project_root, "tank", "config", "core", "schema")

        self.FolderIOReceiverBackup = folder.folder_io.FolderIOReceiver.execute_folder_creation
        folder.folder_io.FolderIOReceiver.execute_folder_creation = execute_folder_creation_proxy

    def tearDown(self):
        
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
        
        self.tk = tank.Tank(self.project_root)
        
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
        
        self.tk = tank.Tank(self.project_root)
        
        self.path_cache = path_cache.PathCache(self.tk.project_path)


    def test_delete_shot_then_recreate(self):
        
        # 1. create fodlers for shot ABC
        # 2. delete shot ABC from SG
        # 3. create a new shot ABC in SG
        # 4. when creating folders, it should delete the previous records and replace with new
        

        self.assertEquals(self.path_cache.get_paths("Shot", self.shot["id"]), [])
        
        folder.process_filesystem_structure(self.tk, 
                                            self.task["type"], 
                                            self.task["id"], 
                                            preview=False, 
                                            engine=None)
        
        # check that it is in the db
        shot_path = os.path.join(self.project_root, "sequences", "seq_code", "shot_code")
        paths_in_db = self.path_cache.get_paths("Shot", self.shot["id"])
        self.assertEquals(paths_in_db, [shot_path])
        
        # change the id of the shot - effectively deleting and creating a shot!
        old_id = self.shot["id"]
        self.shot["id"] = 12345
        
        self.assertEquals(self.path_cache.get_paths("Shot", self.shot["id"]), [])
        
        folder.process_filesystem_structure(self.tk, 
                                            self.task["type"], 
                                            self.task["id"], 
                                            preview=False, 
                                            engine=None)
        
        # now check that the path is associated with the new id and not the old
        shot_path = os.path.join(self.project_root, "sequences", "seq_code", "shot_code")
        paths_in_db = self.path_cache.get_paths("Shot", self.shot["id"])
        self.assertEquals(paths_in_db, [shot_path])
        self.assertEquals(self.path_cache.get_paths("Shot", old_id), [])

        
        
        

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

        self.assertRaises(TankError, 
                          folder.process_filesystem_structure, 
                          self.tk,
                          self.task["type"],
                          self.task["id"],
                          preview=False,
                          engine=None)
        
        # but if I delete the old folder on disk, the folder creation should proceed
        shot_path = os.path.join(self.project_root, "sequences", "seq_code", "shot_code")
        renamed_shot_path = os.path.join(self.project_root, "sequences", "seq_code", "shot_code_renamed")
        shutil.move(shot_path, renamed_shot_path)
        
        folder.process_filesystem_structure(self.tk, 
                                            self.task["type"], 
                                            self.task["id"], 
                                            preview=False, 
                                            engine=None)
        
        new_shot_path = os.path.join(self.project_root, "sequences", "seq_code", "XYZ")
        self.assertTrue( os.path.exists(new_shot_path))
              
     

