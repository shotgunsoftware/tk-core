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
import shutil
import tank
from tank_vendor import yaml
from tank import TankError
from tank import hook
from tank import path_cache
from tank import folder
from tank_test.tank_test_base import *

from . import assert_paths_to_create, execute_folder_creation_proxy

class TestSchemaCreateFolders(TankTestBase):
    def setUp(self, project_tank_name="project_code"):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super().setUp(
            parameters={"project_tank_name": project_tank_name}
        )
        self.setup_fixtures()

        self.seq = {
            "type": "Sequence",
            "id": 2,
            "code": "seq_code",
            "project": self.project,
        }
        self.shot = {
            "type": "Shot",
            "id": 1,
            "code": "shot_code",
            "sg_sequence": self.seq,
            "project": self.project,
        }
        self.step = {
            "type": "Step",
            "id": 3,
            "code": "step_code",
            "entity_type": "Shot",
            "short_name": "step_short_name",
        }
        self.asset = {
            "type": "Asset",
            "id": 4,
            "sg_asset_type": "assettype",
            "code": "assetname",
            "project": self.project,
        }
        self.task = {
            "type": "Task",
            "id": 23,
            "entity": self.shot,
            "step": self.step,
            "project": self.project,
        }

        entities = [self.shot, self.seq, self.step, self.project, self.asset, self.task]

        # Add these to mocked shotgun
        self.add_to_sg_mock_db(entities)

        self.schema_location = os.path.join(
            self.pipeline_config_root, "config", "core", "schema"
        )

        self.FolderIOReceiverBackup = (
            folder.folder_io.FolderIOReceiver.execute_folder_creation
        )
        folder.folder_io.FolderIOReceiver.execute_folder_creation = (
            execute_folder_creation_proxy
        )

    def tearDown(self):

        # important to call base class so it can clean up memory
        super().tearDown()

        # and do local teardown
        folder.folder_io.FolderIOReceiver.execute_folder_creation = (
            self.FolderIOReceiverBackup
        )

    def test_shot(self):
        pass
    def test_white_space(self):
        pass
    def test_unicode(self):
        pass
    def test_illegal_chars(self):
        pass
    def test_asset(self):
        pass
    def test_scene(self):
        pass
    def test_project(self):
        pass
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
        sequence_name = str(sequence_name)

        static_seq = os.path.join(str(self.project_root), "sequences")

        project_root = str(self.project_root)
        expected_paths = [
            project_root,
            os.path.join(project_root, "reference"),
            os.path.join(project_root, "scenes"),
            os.path.join(project_root, "assets"),
            os.path.join(project_root, "reference", "artwork"),
            os.path.join(project_root, "reference", "footage"),
            static_seq,
        ]

        sequence_path = os.path.join(project_root, "sequences", sequence_name)
        if not shot_name:
            shot_name = self.shot["code"]
        shot_name = str(shot_name)
        shot_path = os.path.join(sequence_path, shot_name)

        step_path = os.path.join(shot_path, str(self.step["short_name"]))
        expected_paths.extend([sequence_path, shot_path, step_path])
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
        super().setUp(
            project_tank_name="multi/root/project/name"
        )


class TestSchemaCreateFoldersMultiRoot(TankTestBase):
    """Test paths generated by Schema.create folders for multi-root project."""

    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super().setUp()

        self.setup_multi_root_fixtures()

        self.seq = {
            "type": "Sequence",
            "id": 2,
            "code": "seq_code",
            "project": self.project,
        }
        self.shot = {
            "type": "Shot",
            "id": 1,
            "code": "shot_code",
            "sg_sequence": self.seq,
            "project": self.project,
        }
        self.step = {
            "type": "Step",
            "id": 3,
            "code": "step_code",
            "short_name": "step_short_name",
        }
        self.asset = {
            "type": "Asset",
            "id": 4,
            "sg_asset_type": "assettype",
            "code": "assetname",
            "project": self.project,
        }

        # Add these to mocked shotgun
        self.add_to_sg_mock_db(
            [self.shot, self.seq, self.step, self.project, self.asset]
        )

        self.FolderIOReceiverBackup = (
            folder.folder_io.FolderIOReceiver.execute_folder_creation
        )
        folder.folder_io.FolderIOReceiver.execute_folder_creation = (
            execute_folder_creation_proxy
        )

    def tearDown(self):

        # important to call base class so it can clean up memory
        super().tearDown()

        # and do local teardown
        folder.folder_io.FolderIOReceiver.execute_folder_creation = (
            self.FolderIOReceiverBackup
        )

    def test_shot(self):
        pass
    def test_asset(self):
        pass
    def test_project(self):
        pass
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
        expected_paths.extend([sequence_path, shot_path, step_path])
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
        super().setUp()
        self.setup_fixtures()

        self.seq = {
            "type": "Sequence",
            "id": 2,
            "code": "seq_code",
            "project": self.project,
        }
        self.shot = {
            "type": "Shot",
            "id": 1,
            "code": "shot_code",
            "sg_sequence": self.seq,
            "project": self.project,
        }
        self.step = {
            "type": "Step",
            "id": 3,
            "code": "step_code",
            "short_name": "step_short_name",
        }
        self.asset = {
            "type": "Asset",
            "id": 4,
            "sg_asset_type": "assettype",
            "code": "assetname",
            "project": self.project,
        }
        self.task = {
            "type": "Task",
            "id": 1,
            "content": "this task",
            "entity": self.shot,
            "step": {"type": "Step", "id": 3},
            "project": self.project,
        }

        # Add these to mocked shotgun
        self.add_to_sg_mock_db(
            [self.shot, self.seq, self.step, self.project, self.asset, self.task]
        )

    def test_create_task(self):
        pass
    def test_create_shot(self):
        pass
    def test_create_asset(self):
        pass
    def test_create_project(self):
        pass
    def test_create_sequence(self):
        pass
    def test_wrong_type_entity_ids(self):
        pass
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
        super().setUp()

        self.setup_fixtures(parameters={"core": "core.override/multi_link_core"})

        self.seq = {
            "type": "Sequence",
            "id": 2,
            "code": "seq_code",
            "project": self.project,
        }

        self.shot = {
            "type": "Shot",
            "id": 1,
            "code": "shot_code",
            "sg_sequence": self.seq,
            "project": self.project,
        }

        self.workspace = {
            "type": "CustomEntity02",
            "id": 3,
            "sg_entity": self.shot,
            "project": self.project,
            "code": "workspace_code_shot",
        }

        self.asset = {
            "type": "Asset",
            "id": 4,
            "sg_asset_type": "assettype",
            "code": "assetname",
            "project": self.project,
        }

        self.workspace2 = {
            "type": "CustomEntity02",
            "id": 5,
            "sg_entity": self.asset,
            "project": self.project,
            "code": "workspace_code_asset",
        }

        # need to register the sg_entity link we just made up with the mocker
        field_def = {
            "data_type": {"editable": False, "value": "entity"},
            "description": {"editable": True, "value": ""},
            "editable": {"editable": False, "value": True},
            "entity_type": {"editable": False, "value": "CustomEntity02"},
            "mandatory": {"editable": False, "value": False},
            "name": {"editable": True, "value": "Entity"},
            "properties": {
                "default_value": {"editable": False, "value": None},
                "summary_default": {"editable": True, "value": "none"},
                "valid_types": {"editable": True, "value": ["Shot", "Asset"]},
            },
            "unique": {"editable": False, "value": False},
        }

        # FIXME: The schema is cached in memory for unit tests to reuse, modifying this is BAD.
        self.tk.shotgun._schema = copy.deepcopy(self.tk.shotgun._schema)
        self.tk.shotgun._schema["CustomEntity02"]["sg_entity"] = field_def

        entities = [
            self.shot,
            self.seq,
            self.project,
            self.asset,
            self.workspace,
            self.workspace2,
        ]

        # Add these to mocked shotgun
        self.add_to_sg_mock_db(entities)

        self.schema_location = os.path.join(
            self.pipeline_config_root, "config", "core", "schema"
        )

        self.FolderIOReceiverBackup = (
            folder.folder_io.FolderIOReceiver.execute_folder_creation
        )
        folder.folder_io.FolderIOReceiver.execute_folder_creation = (
            execute_folder_creation_proxy
        )

    def tearDown(self):

        # important to call base class so it can clean up memory
        super().tearDown()

        # and do local teardown
        folder.folder_io.FolderIOReceiver.execute_folder_creation = (
            self.FolderIOReceiverBackup
        )

    def test_shot(self):
        pass
    def test_asset(self):
        pass
class TestFolderCreationPathCache(TankTestBase):
    """
    Tests that the path cache ends up in the correct state when creating folders.
    """

    def setUp(self):
        super().setUp()

        # Use a task based fixtures, as task folders generate two path cache entries with same path, one linked
        # to a task as a primary item, and one linked to a step as a secondary item.
        self.setup_fixtures(
            parameters={"core": "core.override/shotgun_multi_task_core"}
        )

        self.seq = {
            "type": "Sequence",
            "id": 2,
            "code": "seq_code",
            "project": self.project,
        }
        self.shot = {
            "type": "Shot",
            "id": 1,
            "code": "shot_code",
            "sg_sequence": self.seq,
            "project": self.project,
        }
        self.step = {
            "type": "Step",
            "id": 3,
            "code": "step_code",
            "short_name": "step_short_name",
        }
        self.task = {
            "type": "Task",
            "id": 23,
            "entity": self.shot,
            "content": "task1",
            "step": self.step,
            "project": self.project,
        }

        entities = [self.shot, self.seq, self.step, self.project, self.task]

        # Add these to mocked shotgun
        self.add_to_sg_mock_db(entities)

        self.path_cache = path_cache.PathCache(self.tk)

        folder.process_filesystem_structure(
            self.tk, self.task["type"], self.task["id"], preview=False, engine=None
        )

        self.db_cursor = self.path_cache._connection.cursor()

    def tearDown(self):
        # and do local teardown
        # making sure that no file handles remain active
        # leftover handles cause problems on windows!
        self.path_cache.close()
        self.path_cache = None

        # important to call base class so it can clean up memory
        super().tearDown()

    def test_shotgun_path_cache_counts(self):
        pass
class TestFolderCreationEdgeCases(TankTestBase):
    """
    Tests renaming edge cases etc.

    """

    def setUp(self):
        super().setUp()

        self.setup_fixtures()

        self.seq = {
            "type": "Sequence",
            "id": 2,
            "code": "seq_code",
            "project": self.project,
        }
        self.shot = {
            "type": "Shot",
            "id": 1,
            "code": "shot_code",
            "sg_sequence": self.seq,
            "project": self.project,
        }
        self.step = {
            "type": "Step",
            "id": 3,
            "code": "step_code",
            "short_name": "step_short_name",
        }
        self.task = {
            "type": "Task",
            "id": 1,
            "content": "this task",
            "entity": self.shot,
            "step": {"type": "Step", "id": 3},
            "project": self.project,
        }

        # Add these to mocked shotgun
        self.add_to_sg_mock_db(
            [self.shot, self.seq, self.step, self.project, self.task]
        )

        self.path_cache = path_cache.PathCache(self.tk)

    def tearDown(self):

        # and do local teardown
        # making sure that no file handles remain active
        # leftover handles cause problems on windows!
        self.path_cache.close()
        self.path_cache = None

        # important to call base class so it can clean up memory
        super().tearDown()

    def test_delete_shot_then_recreate(self):
        pass
    def test_rename_shot_but_keep_on_disk(self):
        pass
