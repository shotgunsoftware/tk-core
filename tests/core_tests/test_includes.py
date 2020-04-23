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

import tank
from tank_test.tank_test_base import ShotgunTestBase, temp_env_var
from tank_test.tank_test_base import setUpModule  # noqa
from tank.util.includes import _get_includes
from tank_vendor.shotgun_api3.lib import sgsix
from mock import patch


class TestIncludes(ShotgunTestBase):
    """
    Note that these tests will only test the code for the current platform. They
    need to be run on other platforms to get complete coverage.
    """

    _file_name = os.path.join(os.getcwd(), "test.yml")
    _file_dir = os.path.dirname(_file_name)

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
        return _get_includes(self._file_name, {"includes": includes})

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
