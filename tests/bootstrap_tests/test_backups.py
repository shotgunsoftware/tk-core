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
        pass
    def test_cleanup(self):
        pass
    def test_cleanup_with_fail(self):
        pass
    def test_cleanup_read_only(self):
        pass
    def test_local_bundle_cache(self):
        pass
