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

import tank
from tank import context, errors
from tank.util import is_windows
from tank_test.tank_test_base import (
    mock,
    TankTestBase,
    setUpModule,
    only_run_on_windows,
    only_run_on_nix,
)


class TestShotgunRegisterPublish(TankTestBase):
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super().setUp()

        self.setup_fixtures()

        self.storage = {"type": "LocalStorage", "id": 1, "code": "Tank"}

        self.storage_2 = {
            "type": "LocalStorage",
            "id": 2,
            "code": "my_other_storage",
            "mac_path": "/tmp/nix",
            "windows_path": r"x:\tmp\win",
            "linux_path": "/tmp/nix",
        }

        self.storage_3 = {
            "type": "LocalStorage",
            "id": 3,
            "code": "unc paths",
            "windows_path": r"\\server\share",
        }

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.storage, self.storage_2, self.storage_3])

        self.shot = {
            "type": "Shot",
            "name": "shot_name",
            "id": 2,
            "project": self.project,
        }
        self.step = {"type": "Step", "name": "step_name", "id": 4}

        context_data = {
            "tk": self.tk,
            "project": self.project,
            "entity": self.shot,
            "step": self.step,
        }

        self.context = context.Context(**context_data)
        self.path = os.path.join(self.project_root, "foo", "bar")
        self.name = "Test Publish"
        self.version = 1

    def test_local_storage_disabled(self):
        pass
    def test_sequence_abstracted_path(self):
        pass
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.create")
    def test_url_paths(self, create_mock):
        pass
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.create")
    def test_url_paths_host(self, create_mock):
        pass
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.create")
    def test_local_storage_publish(self, create_mock):
        pass
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.create")
    def test_freeform_publish(self, create_mock):
        pass
    def test_no_thumbnail_skips_upload(self):
        pass
    def test_publish_errors(self):
        pass
class TestMultiRoot(TankTestBase):
    def setUp(self):
        super().setUp()
        self.setup_multi_root_fixtures()

        self.shot = {
            "type": "Shot",
            "name": "shot_name",
            "id": 2,
            "project": self.project,
        }
        self.step = {"type": "Step", "name": "step_name", "id": 4}

        context_data = {
            "tk": self.tk,
            "project": self.project,
            "entity": self.shot,
            "step": self.step,
        }

        self.context = context.Context(**context_data)
        self.path = os.path.join(self.project_root, "foo", "bar")
        self.name = "Test Publish"
        self.version = 1

        # mock server caps so we can test local storage mapping for publishes
        class server_capsMock:
            def __init__(self):
                self.version = (7, 0, 1)

        self.mockgun.server_caps = server_capsMock()

        # Prevents an actual connection to a Shotgun site.
        self._server_caps_mock = mock.patch(
            "tank_vendor.shotgun_api3.Shotgun.server_caps"
        )
        self._server_caps_mock.start()
        self.addCleanup(self._server_caps_mock.stop)

    def test_storage_misdirection(self):
        pass
class TestCalcPathCache(TankTestBase):
    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_case_difference(self, get_local_storage_roots):
        pass
    @only_run_on_windows
    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_path_normalization_win_drive_letter(self, get_local_storage_roots):
        pass
    @only_run_on_windows
    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_path_normalization_win_unc(self, get_local_storage_roots):
        pass
    @only_run_on_nix
    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_path_normalization_nix(self, get_local_storage_roots):
        pass
    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_project_names_only_current_project(self, get_local_storage_roots):
        pass
    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_project_names_multiple(self, get_local_storage_roots):
        pass
class TestCalcPathCacheProjectWithSlash(TankTestBase):
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super().setUp({"project_tank_name": "foo/bar"})

    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_multi_project_root(self, get_local_storage_roots):
        pass
