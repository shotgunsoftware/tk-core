# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import uuid
import os

from tank_test.tank_test_base import ShotgunTestBase, temp_env_var
from tank_test.tank_test_base import setUpModule  # noqa


class TestDecorators(ShotgunTestBase):
    """
    Basic environment tests
    """

    def test_temp_env_var_that_didnt_exist(self):
        pass
    def test_temp_env_var_that_already_exist(self):
        pass
