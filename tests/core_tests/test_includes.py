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
import itertools
import sys

import tank
from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
    temp_env_var,
)

from tank.template_includes import _get_includes as get_template_includes
from tank.platform.environment_includes import (
    _resolve_includes as get_environment_includes,
)


class Includes(object):
    """
    Allows to nest the Imp class so that the unit test runner doesn't try to run it.
    """

    class Imp(ShotgunTestBase):
        """
        Tests includes. _resolve_includes needs to be reimplemented by the derived class

        Note that these tests will only test the code for the current platform. They
        need to be run on other platforms to get complete coverage.
        """

        _file_name = os.path.join(os.getcwd(), "test.yml")
        _file_dir = os.path.dirname(_file_name)

        @mock.patch("os.path.exists", return_value=True)
        def test_env_var_only(self, _):
            pass
        @mock.patch("os.path.exists", return_value=True)
        def test_tilde(self, _):
            pass
        @mock.patch("os.path.exists", return_value=True)
        def test_relative_path(self, _):
            pass
        @mock.patch("os.path.exists", return_value=True)
        def test_relative_path_with_env_var(self, _):
            pass
        @mock.patch("os.path.exists", return_value=True)
        def test_path_with_env_var_in_front(self, _):
            pass
        @mock.patch("os.path.exists", return_value=True)
        def test_path_with_env_var_in_middle(self, _):
            pass
        @mock.patch("os.path.exists", return_value=True)
        def test_path_with_multi_os_path(self, _):
            pass
        @mock.patch("os.path.exists", return_value=True)
        def test_path_with_relative_env_var(self, _):
            pass
        def _resolve_includes(self, includes):
            """
            Take the tedium out of calling _get_include
            """
            raise NotImplementedError(
                "TestIncludes._resolve_includes is not implemented."
            )

        def test_missing_file(self):
            pass
        @mock.patch("os.path.exists", return_value=True)
        def test_includes_ordering(self, _):
            pass
# TODO: These tests should be moved within their respective test packages, but because they share
# the same suite of tests there's no easy way to share the suite. However, once we finish the
# refactoring of the include system, I suspect most of these tests will move to the refactored
# framework location and this messiness will go away.


class TestTemplateIncludes(Includes.Imp):
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


class TestEnvironmentIncludes(Includes.Imp):
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
