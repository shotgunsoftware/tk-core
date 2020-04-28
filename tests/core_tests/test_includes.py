# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import with_statement
import os
import itertools
from mock import patch
import re
import logging

# Import the correct StringIO module whether using python 2 or 3
try:
    from StringIO import StringIO
except ModuleNotFoundError:
    from io import StringIO

import tank
from tank_test.tank_test_base import TankTestBase, temp_env_var
from tank_test.tank_test_base import setUpModule  # noqa
from tank.util.includes import get_includes
from tank_vendor.shotgun_api3.lib import sgsix

from tank.platform.environment import Environment
from tank.log import LogManager


class TestIncludes(TankTestBase):
    """
    Note that these tests will only test the code for the current platform. They
    need to be run on other platforms to get complete coverage.
    """

    _file_name = os.path.join(os.getcwd(), "test.yml")
    _file_dir = os.path.dirname(_file_name)

    def setUp(self):
        super(TestIncludes, self).setUp()
        self.setup_fixtures()

    @patch("os.path.exists", return_value=True)
    def test_env_var_only(self, _):
        """
        Validate that a lone environment variable will resolve on all platforms.
        """
        resolved_include = os.path.join(os.getcwd(), "test.yml")
        with temp_env_var(INCLUDE_ENV_VAR=resolved_include):
            os.environ["INCLUDE_ENV_VAR"]
            self.assertEqual(
                self._resolve_includes("$INCLUDE_ENV_VAR"), [resolved_include]
            )

    @patch("os.path.exists", return_value=True)
    def test_tilde(self, _):
        """
        Validate that a tilde will resolve on all platforms.
        """
        include = os.path.join("~", "test.yml")
        resolved_include = os.path.expanduser(include)
        self.assertEqual(self._resolve_includes(include), [resolved_include])

    @patch("os.path.exists", return_value=True)
    def test_relative_path(self, _):
        """
        Validate that relative path are processed correctly
        """
        relative_include = "sub_folder/include.yml"
        self.assertEqual(
            self._resolve_includes(relative_include),
            [os.path.join(self._file_dir, "sub_folder", "include.yml")],
        )

    @patch("os.path.exists", return_value=True)
    def test_relative_path_with_env_var(self, _):
        """
        Validate that relative path with env vars are processed correctly
        """
        relative_include = "$INCLUDE_ENV_VAR/include.yml"
        with temp_env_var(INCLUDE_ENV_VAR=os.getcwd()):
            self.assertEqual(
                self._resolve_includes(relative_include),
                [os.path.join(os.getcwd(), "include.yml")],
            )

    @patch("os.path.exists", return_value=True)
    def test_path_with_env_var_in_front(self, _):
        """
        Validate that relative path are processed correctly on all platforms.
        """
        include = os.path.join("$INCLUDE_ENV_VAR", "include.yml")
        with temp_env_var(INCLUDE_ENV_VAR=os.getcwd()):
            self.assertEqual(
                self._resolve_includes(include),
                [os.path.join(os.getcwd(), "include.yml")],
            )

    @patch("os.path.exists", return_value=True)
    def test_path_with_env_var_in_middle(self, _):
        """
        Validate that relative path are processed correctly on all platforms.
        """
        include = os.path.join(os.getcwd(), "$INCLUDE_ENV_VAR", "include.yml")
        with temp_env_var(INCLUDE_ENV_VAR="includes"):
            self.assertEqual(
                self._resolve_includes(include), [os.path.expandvars(include)]
            )

    @patch("os.path.exists", return_value=True)
    def test_path_with_multi_os_path(self, _):
        """
        Validate that relative path are processed correctly on all platforms.
        """
        paths = {
            "win32": "C:\\test.yml",
            "darwin": "/test.yml",
            "linux2": "/test.yml",
        }
        # Make sure that we are returning the include for the current platform.
        self.assertEqual(
            self._resolve_includes(set(paths.values())),  # get unique values.
            [paths[sgsix.platform]],  # get the value for the current platform
        )

    @patch("os.path.exists", return_value=True)
    def test_path_with_relative_env_var(self, _):
        """
        Validate that relative path are processed correctly on all platforms.
        """
        include = os.path.join("$INCLUDE_ENV_VAR", "include.yml")
        with temp_env_var(INCLUDE_ENV_VAR="sub_folder"):
            self.assertEqual(
                self._resolve_includes(include),
                [os.path.join(os.getcwd(), "sub_folder", "include.yml")],
            )

    def _resolve_includes(self, includes):
        """
        Resolve template includes.
        """
        if isinstance(includes, str):
            includes = [includes]
        return get_includes(self._file_name, {"includes": includes})

    def test_missing_file(self):
        """
        Make sure an exception is raised when the include doesn't exist.
        """
        with self.assertRaisesRegex(tank.TankError, "Include resolve error"):
            self._resolve_includes("dead/path/to/a/file")

    @patch("os.path.exists", return_value=True)
    def test_includes_ordering(self, _):
        """
        Ensure include orders is preserved.
        """
        # Try different permutations of the same set of includes and they should
        # always return in the same order. This is important as values found
        # in later includes override earlier ones.

        # We do permutations here because Python 2 and Python 3 handle
        # set ordering differently.
        for includes in itertools.permutations(["a.yml", "b.yml", "c.yml"]):
            self.assertEqual(
                self._resolve_includes(includes),
                [os.path.join(os.getcwd(), include) for include in includes],
            )

    def test_missing_include(self):
        """
        Test the behaviour and error message when an include file does not exist
        """
        env_file = os.path.join(
            self.project_config, "env", "invalid_settings", "missing_include.yml"
        )
        self.assertRaisesRegex(
            tank.TankError,
            "Include resolve error in .+ resolved to .+ which does not exist!",
            Environment,
            env_file,
        )

    def test_missing_include_path(self):
        """
        Test the behaviour and error message when using a dictionary to define includes and the "path" key is missing
        """
        env_file = os.path.join(
            self.project_config, "env", "invalid_settings", "missing_include_path.yml"
        )
        self.assertRaisesRegex(
            tank.TankError,
            "Failed to process an include in .+ Misisng required 'path' key",
            Environment,
            env_file,
        )

    def test_invalid_include_optional(self):
        """
        Test the behaviour and error message when the "required" parameter of an include is not set to a boolean
        """
        env_file = os.path.join(
            self.project_config,
            "env",
            "invalid_settings",
            "invalid_include_required.yml",
        )
        self.assertRaisesRegex(
            tank.TankError,
            "Invalid 'required' value for the include .+ in .+. Expected a boolean",
            Environment,
            env_file,
        )

    def test_optional_include(self):
        """
        Make sure we log the fact that a non-existent optional include was skipped
        """
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        log_manager = LogManager()
        log_manager.initialize_custom_handler(handler)
        self.addCleanup(lambda: log_manager._root_logger.removeHandler(handler))

        env_file = os.path.join(
            self.project_config, "env", "invalid_settings", "optional_include.yml"
        )
        Environment(env_file)
        self.assertIsNotNone(
            re.search(
                "Skipping optional include.+ resolved to '/not/a/valid/path\.yml' which does not exist!",
                stream.getvalue(),
            )
        )
