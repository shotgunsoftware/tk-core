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
import tank
from tank_vendor import yaml
from tank import TankError
from tank import hook
from tank import folder
from tank_test.tank_test_base import (
    mock,
    TankTestBase,
)

from . import assert_paths_to_create, execute_folder_creation_proxy

# test against a step node where create_with_parent is false


class TestSchemaCreateFoldersSingleStep(TankTestBase):
    def setUp(self):
        pass
    def tearDown(self):
        pass
    def test_shot(self):
        pass
    def test_step_a(self):
        pass
    def test_step_b(self):
        pass
# test against a step node where create_with_parent is true


class TestSchemaCreateFoldersMultiStep(TankTestBase):
    def setUp(self):
        pass
    def tearDown(self):
        pass
    def make_path_list(self):

        expected_paths = []

        sequence_path = os.path.join(self.project_root, "sequences", self.seq["code"])
        sequences_path = os.path.join(self.project_root, "sequences")
        shot_path = os.path.join(sequence_path, self.shot["code"])
        step_path = os.path.join(shot_path, self.step["short_name"])
        step2_path = os.path.join(shot_path, self.step2["short_name"])
        expected_paths.extend(
            [
                self.project_root,
                sequences_path,
                sequence_path,
                shot_path,
                step_path,
                step2_path,
            ]
        )

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
        pass
    def test_step_a(self):
        pass
    def test_step_b(self):
        pass
# make sure that user sandboxes can have step folders inside


class TestSchemaCreateFoldersStepAndUserSandbox(TankTestBase):
    def setUp(self):
        pass
    def tearDown(self):
        pass
    @mock.patch("tank.util.login.get_current_user")
    def test_shot(self, get_current_user):
        pass
    @mock.patch("tank.util.login.get_current_user")
    def test_step_a(self, get_current_user):
        pass
# test against a step node where create_with_parent is false
# and we are using a custom entity for step


class TestSchemaCreateFoldersCustomStep(TankTestBase):
    def setUp(self):
        pass
    def tearDown(self):
        pass
    def test_shot(self):
        pass
    def test_step_a(self):
        pass
    def test_step_b(self):
        pass
