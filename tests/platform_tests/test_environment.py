# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys

from tank.errors import TankError
from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import TankTestBase
from tank_vendor import yaml
from tank.platform.environment import Environment

import copy


class TestEnvironment(TankTestBase):
    """
    Basic environment tests
    """

    def setUp(self):
        pass
    def test_basic_properties(self):
        pass
    def test_engine_settings(self):
        pass
    def test_app_settings(self):
        pass
    def test_engine_meta(self):
        pass
    def test_app_meta(self):
        pass
    def test_engine_missing_location(self):
        pass
    def test_app_missing_location(self):
        pass
    def test_framework_missing_location(self):
        pass
    def test_engine_empty_settings(self):
        pass
    def test_app_empty_settings(self):
        pass
    def test_framework_empty_settings(self):
        pass
    def test_app_empty_location(self):
        pass
    def test_engine_empty_location(self):
        pass
    def test_framework_empty_location(self):
        pass
class TestDumpEnvironment(TankTestBase):
    def setUp(self):
        pass
    def test_dump(self):
        pass
    def test_dump_full(self):
        pass
    def test_dump_sparse(self):
        pass
class TestUpdateEnvironment(TankTestBase):
    """
    Tests yaml environment updates
    """

    def setUp(self):
        pass
    def test_add_engine(self):
        pass
    def test_add_app(self):
        pass
    def test_find_included_engine_location(self):
        pass
    def test_update_engine_settings(self):
        pass
    def test_update_app_settings(self):
        pass
class TestUpdateEnvironmentRuamelYaml(TestUpdateEnvironment):
    """
    Runs the standard environment Update tests with the
    ruamel parser enabled.
    """

    def setUp(self):
        pass
class TestRuamelParser(TankTestBase):
    """
    Tests writing yaml files using the ruamel parser
    """

    def setUp(self):
        pass
    def test_yaml(self):
        pass
class TestPyYamlParser(TankTestBase):
    """
    Tests writing yaml files using the old pyyaml parser
    """

    def setUp(self):
        pass
    def test_yaml(self):
        pass
