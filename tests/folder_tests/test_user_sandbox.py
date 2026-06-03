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


class TestHumanUser(TankTestBase):
    def setUp(self):
        pass
    @mock.patch("tank.util.login.get_current_user")
    def test_not_made_default(self, get_current_user):
        pass
    @mock.patch("tank.util.login.get_current_user")
    def test_made_string(self, get_current_user):
        pass
    @mock.patch("tank.util.login.get_current_user")
    def test_login_not_in_shotgun(self, get_current_user):
        pass
