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
import sys
import unittest

import tank
from tank_test.tank_test_base import ShotgunTestBase, setUpModule  # noqa


def get_file_list(folder, prefix):
    """
    Return a relative listing of files in a folder.

    :param folder: Folder to enumerate
    :param prefix: Prefix to exclude from all paths
    :return: list of files in folder with prefix excluded.
    """
    items = []
    for x in os.listdir(folder):
        full_path = os.path.join(folder, x)
        test_centric_path = full_path[len(prefix) :]
        # translate to platform agnostic path
        test_centric_path = test_centric_path.replace(os.path.sep, "/")
        items.append(test_centric_path)
        if os.path.isdir(full_path):
            items.extend(get_file_list(full_path, prefix))
    return items


class TestUnzipping(ShotgunTestBase):
    """
    Tests the tank.util.zip.unzip_file() method
    """

    def setUp(self):
        """
        Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super().setUp()

        # fixtures location for zips
        self.zip_file_location = os.path.join(self.fixtures_root, "misc", "zip")

        # make sure assert diffs are unlimited
        self.maxDiff = None

    def test_std_unzip(self):
        """
        Tests unzipping of a standard app store core bundle
        """
        zip = os.path.join(self.zip_file_location, "tank_core.zip")
        txt = os.path.join(self.zip_file_location, "tank_core.txt")
        with open(txt) as txt_file:
            expected_output = txt_file.read().split("\n")

        output_path_1 = os.path.join(self.project_root, "core_zip_test_1")
        tank.util.zip.unzip_file(zip, output_path_1)
        self.assertEqual(
            set(get_file_list(output_path_1, output_path_1)), set(expected_output)
        )

        # if we enable auto_detect we should get the same result
        output_path_2 = os.path.join(self.project_root, "core_zip_test_2")
        tank.util.zip.unzip_file(zip, output_path_2, auto_detect_bundle=True)
        self.assertEqual(
            set(get_file_list(output_path_2, output_path_2)), set(expected_output)
        )

    def test_single_folder_unzip(self):
        """
        Tests unzipping an archive where everything resides in a subfolder
        """
        zip = os.path.join(self.zip_file_location, "zip_with_root_folder.zip")
        txt_std = os.path.join(self.zip_file_location, "zip_with_root_folder.txt")
        expected_output = open(txt_std).read().split("\n")
        txt_auto = os.path.join(self.zip_file_location, "zip_with_root_auto_detect.txt")
        expected_output_auto = open(txt_auto).read().split("\n")

        output_path_1 = os.path.join(self.project_root, "config_zip_test_1")
        tank.util.zip.unzip_file(zip, output_path_1)
        self.assertEqual(
            set(get_file_list(output_path_1, output_path_1)), set(expected_output)
        )

        # if we enable auto_detect we should get the same result
        output_path_2 = os.path.join(self.project_root, "config_zip_test_2")
        tank.util.zip.unzip_file(zip, output_path_2, auto_detect_bundle=True)
        self.assertEqual(
            set(get_file_list(output_path_2, output_path_2)), set(expected_output_auto)
        )

    def test_single_file_unzip(self):
        """
        Tests unzipping an archive with a single file (edge case)
        """
        zip = os.path.join(self.zip_file_location, "single_file.zip")

        output_path_1 = os.path.join(self.project_root, "single_zip_test_1")
        tank.util.zip.unzip_file(zip, output_path_1)

        output_path_2 = os.path.join(self.project_root, "single_zip_test_2")
        tank.util.zip.unzip_file(zip, output_path_2, auto_detect_bundle=True)

        self.assertEqual(
            set(get_file_list(output_path_1, output_path_1)),
            set(get_file_list(output_path_2, output_path_2)),
        )

        # if we enable auto_detect we should get the same result
        self.assertEqual(
            set(get_file_list(output_path_2, output_path_2)), set(["/info.yml"])
        )


class TestToExtendedPath(ShotgunTestBase):
    """
    Tests the tank.util.zip._to_extended_path() helper.
    """

    _LONG_ABS_PATH = "C:\\" + "a" * 257  # 260 chars, drive-letter absolute
    _LONG_UNC_PATH = "\\\\server\\share\\" + "a" * 245  # 260 chars, UNC

    def test_short_path_unchanged(self):
        """A path under 260 characters is returned unchanged on all platforms."""
        path = "C:\\short\\path\\file.txt"
        self.assertEqual(tank.util.zip._to_extended_path(path), path)

    def test_relative_path_unchanged(self):
        """A relative path >= 260 characters must NOT receive the prefix."""
        path = "relative\\" + "a" * 257  # long but relative
        self.assertFalse(os.path.isabs(path))
        self.assertEqual(tank.util.zip._to_extended_path(path), path)

    @unittest.skipUnless(sys.platform == "win32", "Windows-only behaviour")
    def test_long_absolute_path_prefixed_on_windows(self):
        """A long drive-letter path on Windows receives the \\\\?\\ prefix."""
        result = tank.util.zip._to_extended_path(self._LONG_ABS_PATH)
        self.assertTrue(result.startswith("\\\\?\\"))
        self.assertEqual(result, "\\\\?\\" + self._LONG_ABS_PATH)

    @unittest.skipUnless(sys.platform == "win32", "Windows-only behaviour")
    def test_already_prefixed_path_unchanged(self):
        """A path that already has the \\\\?\\ prefix is not double-prefixed."""
        prefixed = "\\\\?\\" + self._LONG_ABS_PATH
        self.assertEqual(tank.util.zip._to_extended_path(prefixed), prefixed)

    @unittest.skipUnless(sys.platform == "win32", "Windows-only behaviour")
    def test_long_unc_path_prefixed_with_unc_prefix(self):
        """A long UNC path receives \\\\?\\UNC\\ prefix, not \\\\?\\\\\\\\."""
        result = tank.util.zip._to_extended_path(self._LONG_UNC_PATH)
        self.assertTrue(result.startswith("\\\\?\\UNC\\"))
        self.assertEqual(result, "\\\\?\\UNC\\" + self._LONG_UNC_PATH[2:])

    @unittest.skipUnless(sys.platform == "win32", "Windows-only behaviour")
    def test_already_extended_unc_path_unchanged(self):
        """A path already using \\\\?\\UNC\\ is not double-prefixed."""
        prefixed = "\\\\?\\UNC\\" + self._LONG_UNC_PATH[2:]
        self.assertEqual(tank.util.zip._to_extended_path(prefixed), prefixed)

    @unittest.skipUnless(sys.platform == "win32", "Windows-only behaviour")
    def test_drive_less_rooted_path_unchanged(self):
        """A drive-less rooted path (\\foo) must NOT receive the prefix."""
        path = "\\" + "a" * 259  # rooted but no drive letter, >= 260 chars
        self.assertEqual(tank.util.zip._to_extended_path(path), path)

    @unittest.skipIf(sys.platform == "win32", "Non-Windows behaviour")
    def test_long_absolute_path_unchanged_on_non_windows(self):
        """A long absolute path on non-Windows platforms is returned unchanged."""
        path = "/" + "a" * 260
        self.assertEqual(tank.util.zip._to_extended_path(path), path)
