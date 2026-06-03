# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import inspect
from io import StringIO
import logging
import os
import shutil
import tempfile
from unittest import mock

import tank
from tank.errors import TankError, TankHookMethodDoesNotExistError
from tank.platform import application, validation
from tank.template import Template
from tank_test.tank_test_base import *


class TestApplication(TankTestBase):
    """
    Base class for Application tests
    """

    def setUp(self):
        pass
    def tearDown(self):
        pass
class TestAppFrameworks(TestApplication):
    """
    Tests for framework related operations
    """

    def test_frameworks_named_after_info_yml_name(self):
        pass
    def test_minimum_version(self):
        pass
class TestGetApplication(TestApplication):
    """
    Tests the application.get_application method
    """

    def test_bad_app_path(self):
        pass
    def test_good_path(self):
        pass
class TestGetSetting(TestApplication):
    """
    Tests settings retrieval
    """

    def setUp(self):
        pass
    def test_get_setting(self):
        pass
class TestDataclassHook(TestApplication):
    """
    Test loading, executing and calling ``dataclass_hook``.
    """

    def test_execute(self):
        pass
    def test_legacy_format(self):
        pass
class TestExecuteHookByName(TestApplication):
    """
    Tests execute_hook_by_name
    """

    def test_legacy_format_old_method(self):
        pass
    def test_legacy_format(self):
        pass
    def test_legacy_format_2(self):
        pass
    def test_config(self):
        pass
    def test_engine(self):
        pass
    def test_self(self):
        pass
    # calling `execute_hook_method` for a method that does not exist in the hook
    # should raise the TankHookMethodDoesNotExistError exception
    def test_no_method(self):
        pass
class TestExecuteHook(TestApplication):
    """
    Tests the app.execute_hook method
    """

    def test_standard_format(self):
        pass
    def test_custom_method(self):
        pass
    def test_create_instance(self):
        pass
    def test_parent(self):
        pass
    def test_sgtk(self):
        pass
    def test_logger(self):
        pass
    def test_disk_location(self):
        pass
    def test_inheritance_disk_location(self):
        pass
    def test_self_format(self):
        pass
    def test_config_format(self):
        pass
    def test_engine_format(self):
        pass
    def test_framework_format(self):
        pass
    def test_default_format(self):
        pass
    def test_env_var_format(self):
        pass
    def test_inheritance(self):
        pass
    def test_inheritance_2(self):
        pass
    def test_inheritance_3(self):
        pass
    def test_inheritance_old_style(self):
        pass
    def test_inheritance_old_style_fails(self):
        pass
    def test_new_style_config_old_style_hook(self):
        pass
    def test_default_syntax_with_new_style_hook(self):
        pass
    def test_default_syntax_missing_implementation(self):
        pass
    # sparse tests

    def test_hooks_sparse(self):
        pass
    def test_default_values(self):
        pass
class TestRequestFolder(TestApplication):
    def test_request_folder(self):
        pass
class TestHookCache(TestApplication):
    """
    Check that the hooks cache is cleared when an engine is restarted.
    """

    def test_call_hook(self):
        pass
class TestProperties(TestApplication):
    def test_properties(self):
        pass
class TestBundleDataCache(TestApplication):
    """
    Test bundle data cache paths
    """

    def test_data_path(self):
        pass
