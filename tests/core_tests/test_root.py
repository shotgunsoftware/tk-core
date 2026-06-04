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
import copy

from tank_vendor import yaml
from tank_test.tank_test_base import TankTestBase, setUpModule  # noqa

import tank
from tank import TankError
from tank.util import is_linux, is_macos, is_windows


class TestGetProjectRoots(TankTestBase):
    def setUp(self):
        super().setUp()

        # Tests are updating the roots.yml file, so we'll turn this into an installed configuration.
        self.setup_fixtures(parameters={"installed_config": True})
        self.root_file_path = os.path.join(
            self.pipeline_config_root, "config", "core", "roots.yml"
        )

        # TODO make os specific paths
        self.roots = {"primary": {}, "publish": {}, "render": {}}
        for os_name in ["linux_path", "mac_path"]:
            self.roots["primary"][os_name] = os.path.dirname(self.project_root).replace(
                os.sep, "/"
            )
            self.roots["publish"][os_name] = os.path.join(
                self.tank_temp, "publish"
            ).replace(os.sep, "/")
            self.roots["render"][os_name] = os.path.join(
                self.tank_temp, "render"
            ).replace(os.sep, "/")
        for os_name in ["windows_path"]:
            self.roots["primary"][os_name] = os.path.dirname(self.project_root).replace(
                os.sep, "\\"
            )
            self.roots["publish"][os_name] = os.path.join(
                self.tank_temp, "publish"
            ).replace(os.sep, "\\")
            self.roots["render"][os_name] = os.path.join(
                self.tank_temp, "render"
            ).replace(os.sep, "\\")

        # the roots file will be written by each test

    def test_file_missing(self):
        pass
    def test_paths(self):
        pass
    def test_all_paths(self):
        pass
    def test_flexible_primary(self):
        pass
class TestGetPrimaryRoot(TankTestBase):
    def setUp(self):
        super().setUp()

        self.setup_multi_root_fixtures()

        # create shot and asset data
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
        self.asset = {
            "type": "Asset",
            "id": 4,
            "sg_asset_type": "assettype",
            "code": "assetname",
            "project": self.project,
        }

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.shot, self.seq, self.project, self.asset])

        # Write path in primary root tree
        self.tk.create_filesystem_structure("Shot", 1)
        # Write path in alternate root tree
        self.tk.create_filesystem_structure("Asset", 4)

    def test_alt_path(self):
        pass
    def test_primary(self):
        pass
    def test_non_project_path(self):
        pass
