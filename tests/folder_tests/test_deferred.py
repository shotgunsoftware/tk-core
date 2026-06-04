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
import shutil
import tank
from tank_vendor import yaml
from tank import TankError
from tank import hook
from tank import folder
from tank_test.tank_test_base import *


class TestDeferredFolderCreation(TankTestBase):
    """Test deferring of folder creation."""

    def setUp(self):
        super().setUp()
        self.setup_fixtures(parameters={"core": "core.override/deferred_core"})

        self.shot = {
            "type": "Shot",
            "id": 1,
            "code": "shot_code",
            "project": self.project,
        }

        self.asset = {
            "type": "Asset",
            "id": 4,
            "sg_asset_type": "assettype",
            "code": "assetname",
            "project": self.project,
        }

        self.add_to_sg_mock_db([self.shot, self.asset])

        self.deferred_absent = os.path.join(
            self.project_root, "deferred_absent", "shot_code"
        )
        self.deferred_false = os.path.join(
            self.project_root, "deferred_false", "shot_code"
        )
        self.deferred_specified = os.path.join(
            self.project_root, "deferred_specified", "shot_code"
        )
        self.deferred_specified_2 = os.path.join(
            self.project_root, "deferred_specified_2", "shot_code"
        )
        self.deferred_true = os.path.join(
            self.project_root, "deferred_true", "shot_code"
        )
        self.deferred_asset_type = os.path.join(self.project_root, "assettype")
        self.deferred_asset = os.path.join(self.deferred_asset_type, "assetname")

    def test_option_absent(self):
        pass
    def test_specify_option(self):
        pass
    def test_specify_option_2(self):
        pass
    def test_list_field(self):
        pass
    def test_asset(self):
        pass
