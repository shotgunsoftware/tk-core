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



g_paths_created = []

class FolderIOReceiverProxy(object):
    """
    Class that encapsulates all the IO operations from the various folder classes.
    """
    
    def __init__(self, tk, preview):
        """
        Constructor
        """
        global g_paths_created
        g_paths_created = []
        self._tk = tk
        self._preview_mode = preview
        self._computed_items = list()
        
    def get_computed_items(self):
        """
        Returns list of files and folders that have been computed by the folder creation
        """
        return self._computed_items
                
    def add_entry_to_cache_db(self, path, entity_type, entity_id, entity_name):
        """
        Adds entity to database. 
        """
        
    def make_folder(self, path):
        """
        Calls make folder callback.
        """
        self._computed_items.append(path)
        g_paths_created.append(path)
    
    def copy_file(self, src_path, target_path):
        """
        Calls copy file callback.
        """
        self._computed_items.append(target_path)
        g_paths_created.append(target_path)            
    
    def prepare_project_root(self, root_path):
        
        if root_path != self._tk.project_path:
            g_paths_created.append(root_path)
            g_paths_created.append( os.path.join(root_path, "tank"))
            g_paths_created.append( os.path.join(root_path, "tank", "config"))







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

        self.FolderIOReceiverBackup = folder.schema.FolderIOReceiver
        folder.schema.FolderIOReceiver = FolderIOReceiverProxy

    def tearDown(self):
        
        folder.schema.FolderIOReceiver = self.FolderIOReceiverBackup


    def test_shot(self):
        """Tests paths used in making a shot are as expected."""
        expected_paths = self._construct_shot_paths()
        
        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine=None)        
        self.assert_paths_to_create(expected_paths)

    def test_white_space(self):
        # make illegal value
        self.shot["code"] = "name with spaces"
        
        expected_paths = self._construct_shot_paths(shot_name="name-with-spaces")

        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine=None)        
        
        self.assert_paths_to_create(expected_paths)

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
            
            self.assert_paths_to_create(expected_paths)

    def test_asset(self):
        """Tests paths used in making a asset are as expected."""
        # expected paths here are based on sg_standard start-config
        # define paths we expect for entities
        asset_type_path = os.path.join(self.project_root, "assets", self.asset["sg_asset_type"])
        
        asset_path = os.path.join(asset_type_path, self.asset["code"])
        
        step_path = os.path.join(asset_path, self.step["short_name"])
        
        expected_paths = [asset_type_path, asset_path, step_path]
        
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
        
        self.assert_paths_to_create(expected_paths)
    
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
        
        expected_paths = []
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
        
        self.assert_paths_to_create(expected_paths)

    def test_project(self):
        """Tests paths used in making a project are as expected."""
        # paths based on sg_standard starter config
        expected_paths = []
        expected_paths.append(os.path.join(self.project_root, "sequences"))
        expected_paths.append(os.path.join(self.project_root, "scenes"))
        expected_paths.append(os.path.join(self.project_root, "assets"))
        expected_paths.append(os.path.join(self.project_root, "assets", self.asset["sg_asset_type"]))
        expected_paths.append(os.path.join(self.project_root, "reference"))
        expected_paths.append(os.path.join(self.project_root, "reference", "artwork"))
        expected_paths.append(os.path.join(self.project_root, "reference", "footage"))

        folder.process_filesystem_structure(self.tk, 
                                            self.project["type"], 
                                            self.project["id"],  
                                            preview=False,
                                            engine=None)        
        
        self.assert_paths_to_create(expected_paths)

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

        sequence_path = os.path.join(self.project_root, "sequences", sequence_name)
        if not shot_name:
            shot_name = self.shot["code"]
        shot_path = os.path.join(sequence_path, shot_name)

        step_path = os.path.join(shot_path, self.step["short_name"])
        expected_paths = [sequence_path, shot_path, step_path]
        # add non-entity paths
        expected_paths.append(os.path.join(step_path, "publish"))
        expected_paths.append(os.path.join(step_path, "images"))
        expected_paths.append(os.path.join(step_path, "review"))
        expected_paths.append(os.path.join(step_path, "work"))
        expected_paths.append(os.path.join(step_path, "work", "snapshots"))
        expected_paths.append(os.path.join(step_path, "work", "workspace.mel"))
        expected_paths.append(os.path.join(step_path, "out"))
        return expected_paths


    def assert_paths_to_create(self, expected_paths):
        """
        No file system operations are performed.
        """
        # Check paths sent to make_folder
        for expected_path in expected_paths:
            if expected_path not in g_paths_created:
                assert False, "\n%s\nnot found in: [\n%s]" % (expected_path, "\n".join(g_paths_created))
        for actual_path in g_paths_created:
            if not any(x.startswith(actual_path) for x in expected_paths):
                assert False, "Unexpected path slated for creation: %s" % actual_path


                                
                                
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

        self.FolderIOReceiverBackup = folder.schema.FolderIOReceiver
        folder.schema.FolderIOReceiver = FolderIOReceiverProxy

    def tearDown(self):
        
        folder.schema.FolderIOReceiver = self.FolderIOReceiverBackup


    def test_shot(self):
        """Tests paths used in making a shot are as expected."""
        expected_paths = self._construct_shot_paths()
        
        folder.process_filesystem_structure(self.tk, 
                                            self.shot["type"], 
                                            self.shot["id"], 
                                            preview=False,
                                            engine=None)        
        
        self.assert_paths_to_create(expected_paths)
        

    def test_asset(self):
        """Tests paths used in making a asset are as expected."""
        # expected paths here are based on sg_standard start-config
        # define paths we expect for entities
        asset_folder_name = "%s_%s" % (self.asset["sg_asset_type"], self.asset["code"])
        asset_path = os.path.join(self.alt_root_1, "assets", asset_folder_name)
        step_path = os.path.join(asset_path, self.step["short_name"])
        expected_paths = [asset_path, step_path]
        # config path
        expected_paths.append(os.path.join(self.alt_root_1, "tank", "config"))
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

        self.assert_paths_to_create(expected_paths)

    def test_project(self):
        """
        Tests paths used in making a project are as expected when single project directory
        with no yaml file exits.
        """
        # paths based on sg_standard starter config modified to be multi-project
        expected_paths = []
        expected_paths.append(os.path.join(self.project_root, "sequences"))
        expected_paths.append(os.path.join(self.project_root, "reference"))
        expected_paths.append(os.path.join(self.project_root, "reference", "artwork"))
        expected_paths.append(os.path.join(self.project_root, "reference", "footage"))

        expected_paths.append(os.path.join(self.alt_root_1, "tank"))
        expected_paths.append(os.path.join(self.alt_root_1, "tank", "config"))
        expected_paths.append(os.path.join(self.alt_root_1, "assets"))
        expected_paths.append(os.path.join(self.alt_root_1, "alternate_reference"))
                
        folder.process_filesystem_structure(self.tk, 
                                            self.project["type"], 
                                            self.project["id"], 
                                            preview=False,
                                            engine=None)        
        
        self.assert_paths_to_create(expected_paths)

    def _construct_shot_paths(self, sequence_name=None, shot_name=None, step_name=None):
        """
        Constructs expected paths for a shot based on the multi root test schema

        :param sequence_name: Override for the name of the sequence directory.
        :param shot_name: Override for the name of the shot directory.
        :param step_name: Override for the name of the step directory.

        :returns: List of paths
        """
        # expected paths here are based on sg_standard start-config
        # define paths we expect for entities
        if not sequence_name:
            sequence_name = self.seq["code"]

        sequence_path = os.path.join(self.project_root, "sequences", sequence_name)
        if not shot_name:
            shot_name = self.shot["code"]
        shot_path = os.path.join(sequence_path, shot_name)

        step_path = os.path.join(shot_path, self.step["short_name"])
        expected_paths = [sequence_path, shot_path, step_path]
        # add non-entity paths
        expected_paths.append(os.path.join(step_path, "publish"))
        expected_paths.append(os.path.join(step_path, "images"))
        expected_paths.append(os.path.join(step_path, "review"))
        expected_paths.append(os.path.join(step_path, "work"))
        expected_paths.append(os.path.join(step_path, "work", "snapshots"))
        expected_paths.append(os.path.join(step_path, "out"))
        return expected_paths

    def assert_paths_to_create(self, expected_paths):
        """
        No file system operations are performed.
        """
        for expected_path in expected_paths:
            if expected_path not in g_paths_created:
                assert False, "\n%s\nnot found in: [\n%s]" % (expected_path, "\n".join(g_paths_created))
        
        for actual_path in g_paths_created:
            if not any(x.startswith(actual_path) for x in expected_paths):
                assert False, "Unexpected path slated for creation: %s" % actual_path

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
              
              
     


