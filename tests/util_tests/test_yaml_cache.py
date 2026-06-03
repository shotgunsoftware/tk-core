# Copyright (c) 2015 Shotgun Software Inc.
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

import sgtk
from sgtk.util.yaml_cache import YamlCache
from sgtk import TankError
from tank_vendor import yaml
from tank_test.tank_test_base import ShotgunTestBase
from tank_test.tank_test_base import setUpModule  # noqa


class TestYamlCache(ShotgunTestBase):
    """
    Tests to ensure that the YamlCache behaves correctly
    """

    def __init__(self, *args, **kwargs):
        """
        Construction
        """
        ShotgunTestBase.__init__(self, *args, **kwargs)

        # data root for all test data:
        self._data_root = os.path.join(self.fixtures_root, "misc", "yaml_cache")

    def test_empty_yml_return(self):
        pass
    def test_get_incorrect_path(self):
        pass
    def test_get_valid_path(self):
        pass
