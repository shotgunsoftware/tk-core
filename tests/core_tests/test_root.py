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
        pass
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
        pass
    def test_alt_path(self):
        pass
    def test_primary(self):
        pass
    def test_non_project_path(self):
        pass
