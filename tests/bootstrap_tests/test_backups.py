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
import fnmatch
import stat
import sgtk
from sgtk.pipelineconfig_utils import get_metadata
from tank.util import is_windows
from shutil import copytree

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
    temp_env_var,
)


def ignore_patterns(*patterns):
    """Function that can be used as copytree() ignore parameter.

    Patterns is a sequence of glob-style patterns
    that are used to exclude files"""

    def _ignore_patterns(path, names):
        ignored_names = []
        for pattern in patterns:
            ignored_names.extend(fnmatch.filter(names, pattern))
        return set(ignored_names)

    return _ignore_patterns


class TestBackups(ShotgunTestBase):
    def setUp(self):
        super().setUp()

        pathHead, pathTail = os.path.split(__file__)
        self._core_repo_path = os.path.join(pathHead, "..", "..")
        self._temp_test_path = os.path.join(
            pathHead, "..", "fixtures", "bootstrap_tests", "test_backups"
        )
        if (
            is_windows()
        ):  # On Windows, filenames in temp path are too long for straight copy ...
            core_copy_path = os.path.join(self.tank_temp, "tk-core-copy")
            if not os.path.exists(core_copy_path):
                # ... so avoid copying ignore folders to avoid errors when copying the core repo
                copytree(
                    self._core_repo_path,
                    core_copy_path,
                    ignore=ignore_patterns("tests", "docs", "coverage_html_report"),
                )
            self._core_repo_path = core_copy_path

    def test_cleanup(self):
        pass
    def test_cleanup_with_fail(self):
        pass
    def test_cleanup_read_only(self):
        pass
    def test_local_bundle_cache(self):
        pass
