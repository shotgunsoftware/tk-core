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
from tank_test.tank_test_base import setUpModule # noqa
from tank_test.tank_test_base import TankTestBase


class TestFolderConfiguration(TankTestBase):
    """
    Tests initialization of Schema class
    """

    def setUp(self):
        pass
    def test_project_root_mismatch(self):
        pass
    def test_project_one_yml_missing(self):
        pass
