# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import logging
import os

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    TankTestBase,
)

from tank.platform import create_engine_launcher
from tank.platform import SoftwareLauncher
from tank.platform import SoftwareVersion
from tank.platform import LaunchInformation

from tank.errors import TankEngineInitError


class TestEngineLauncher(TankTestBase):
    def setUp(self):
        super().setUp()
        self.setup_fixtures()

        # setup shot
        seq = {"type": "Sequence", "name": "seq_name", "id": 3}
        seq_path = os.path.join(self.project_root, "sequences/Seq")
        self.add_production_path(seq_path, seq)

        self.shot = {
            "type": "Shot",
            "name": "shot_name",
            "id": 2,
            "project": self.project,
        }
        shot_path = os.path.join(seq_path, "shot_code")
        self.add_production_path(shot_path, self.shot)

        self.step = {"type": "Step", "name": "step_name", "id": 4}
        self.shot_step_path = os.path.join(shot_path, "step_name")
        self.add_production_path(self.shot_step_path, self.step)

        self.context = self.tk.context_from_path(self.shot_step_path)
        self.engine_name = "test_engine"

        self.task = {
            "type": "Task",
            "id": 23,
            "entity": self.shot,
            "step": self.step,
            "project": self.project,
        }

        entities = [self.task]

        # Add these to mocked shotgun
        self.add_to_sg_mock_db(entities)

    def test_create_launcher(self):
        pass
    def test_launcher_scan_software(self):
        pass
    def test_get_standard_plugin_environment(self):
        pass
    def test_get_standard_plugin_environment_empty(self):
        pass
    def test_minimum_version(self):
        pass
    def test_version_supported(self):
        pass
    def test_product_supported(self):
        pass
    def test_is_supported(self):
        pass
    def test_launcher_prepare_launch(self):
        pass
    def test_glob_and_match(self):
        pass
class TestSoftwareVersion(TankTestBase):
    def setUp(self):
        super().setUp()

        self._version = "v293.49.2.dev"
        self._product = "My Custom App"
        self._path = "/my/path/to/app/{version}/my_custom_app"
        self._icon = "%s/icon.png" % self._path
        self.args = ["--42"]

    def test_init_software_version(self):
        pass
class TestLaunchInformation(TankTestBase):
    def setUp(self):
        super().setUp()

        self._path = "/my/path/to/app/{version}/my_custom_app"
        self._args = "-t 1-30 --show_all -v --select ship"
        self._environment = {
            "ENV_STR_KEY": "custom enviorment string value",
            "ENV_INT_KEY": 1001,
            "ENV_FLT_KEY": 3.1415,
        }

    def test_init_launch_information(self):
        pass
