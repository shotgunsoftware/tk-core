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
import sys

import tank
from tank_test.tank_test_base import TankTestBase, setUpModule, temp_env_var
from tank.template_includes import _get_includes as get_template_includes
from tank.platform.environment_includes import _resolve_includes as get_environment_includes
from mock import patch


class TestIncludes(object):
    """
    Allows to nest the Imp class so that the unit test runner doesn't try to run it.
    """

    class Imp(TankTestBase):
        """
        Tests includes. _resolve_includes needs to be reimplemented by the derived class

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
                    self._resolve_includes("$INCLUDE_ENV_VAR"),
                    [resolved_include]
                )

        @patch("os.path.exists", return_value=True)
        def test_tilde(self, _):
            """
            Validate that a tilde will resolve on all platforms.
            """
            include = os.path.join("~", "test.yml")
            resolved_include = os.path.expanduser(include)
            self.assertEqual(
                self._resolve_includes(include),
                [resolved_include]
            )

        @patch("os.path.exists", return_value=True)
        def test_relative_path(self, _):
            """
            Validate that relative path are processed correctly
            """
            relative_include = "sub_folder/include.yml"
            self.assertEqual(
                self._resolve_includes(relative_include),
                [os.path.join(self._file_dir, "sub_folder", "include.yml")]
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
                    [os.path.join(os.getcwd(), "include.yml")]
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
                    [os.path.join(os.getcwd(), "include.yml")]
                )

        @patch("os.path.exists", return_value=True)
        def test_path_with_env_var_in_middle(self, _):
            """
            Validate that relative path are processed correctly on all platforms.
            """
            include = os.path.join(os.getcwd(), "$INCLUDE_ENV_VAR", "include.yml")
            with temp_env_var(INCLUDE_ENV_VAR="includes"):
                self.assertEqual(
                    self._resolve_includes(include),
                    [os.path.expandvars(include)]
                )

        @patch("os.path.exists", return_value=True)
        def test_path_with_multi_os_path(self, _):
            """
            Validate that relative path are processed correctly on all platforms.
            """
            paths = {
                "win32": "C:\\test.yml",
                "darwin": "/test.yml",
                "linux2": "/test.yml"
            }
            # Make sure that we are returning the include for the current platform.
            self.assertEqual(
                self._resolve_includes(set(paths.values())), # get unique values.
                [paths[sys.platform]] # get the value for the current platform
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
                    [os.path.join(os.getcwd(), "sub_folder", "include.yml")]
                )

        def _resolve_includes(self, includes):
            """
            Take the tedium out of calling _get_include
            """
            raise NotImplementedError("TestIncludes._resolve_includes is not implemented.")

        def test_missing_file(self):
            """
            Make sure an exception is raised when the include doesn't exist.
            """
            with self.assertRaisesRegexp(tank.TankError, "Include resolve error"):
                self._resolve_includes("dead/path/to/a/file")


# TODO: These tests should be move within the respective test package, but because they share
# the same suite of tests there's no easy way to share the suite. However, once we finish the
# refactoring of the include system, I suspect most of these tests will move to the refactored
# framework location and this messiness will go away.

class TestTemplateIncludes(TestIncludes.Imp):
    """
    Tests template includes.
    """

    def _resolve_includes(self, includes):
        """
        Resolve template includes.
        """
        if isinstance(includes, str):
            includes = [includes]
        return get_template_includes(self._file_name, {"includes": includes})


class TestEnvironmentIncludes(TestIncludes.Imp):
    """
    Tests environment includes.
    """

    def _resolve_includes(self, includes):
        """
        Resolve environment includes.
        """
        if isinstance(includes, str):
            includes = [includes]
        return get_environment_includes(self._file_name, {"includes": includes}, None)
