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
        pass
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
        pass
    def test_init_software_version(self):
        pass
class TestLaunchInformation(TankTestBase):
    def setUp(self):
        pass
    def test_init_launch_information(self):
        pass
