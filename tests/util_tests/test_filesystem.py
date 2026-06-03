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
from tank.util import is_linux, is_macos, is_windows
from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    TankTestBase,
)

import tank.util.filesystem as fs

import subprocess  # noqa
import shutil
import stat


class TestFileSystem(TankTestBase):
    def setUp(self):
        pass
    def test_safe_delete_non_existing_folder(self):
        pass
    def test_safe_delete_folder(self):
        pass
    def test_safe_delete_folder_with_file_in_use(self):
        pass
    def test_safe_delete_folder_with_read_only_items(self):
        pass
    def test_unused_path(self):
        pass
    def test_copy_file(self):
        pass
    def test_copy_folder(self):
        pass
class TestOpenInFileBrowser(TankTestBase):
    """
    Tests the open_file_browser functionality
    """

    def setUp(self):
        pass
    def test_bad_path(self):
        pass
    @mock.patch("subprocess.call", return_value=0)
    def test_folder(self, subprocess_mock):
        pass
    @mock.patch("subprocess.call", return_value=1234)
    def test_failed_folder(self, _):
        pass
    @mock.patch("subprocess.call", return_value=0)
    def test_file(self, subprocess_mock):
        pass
    @mock.patch("subprocess.call", return_value=1234)
    def test_failed_file(self, _):
        pass
    @mock.patch("subprocess.call", return_value=0)
    def test_sequence(self, subprocess_mock):
        pass
