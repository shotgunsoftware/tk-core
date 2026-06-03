# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
)

from tank.util import EnvironmentVariableFileLookupError
from tank.util.user_settings import UserSettings
from sgtk import TankError


class UserSettingsTests(ShotgunTestBase):
    """
    Tests functionality around toolkit.ini
    """

    def setUp(self):
        pass
    def test_empty_file(self):
        pass
    def test_filled_file(self):
        pass
    def test_empty_settings(self):
        pass
    def test_custom_settings(self):
        pass
    def test_boolean_setting(self):
        pass
    def test_settings_enumeration(self):
        pass
    def test_integer_setting(self):
        pass
    def test_environment_variable_expansions(self):
        pass
    def test_bad_environment_variable(self):
        pass
