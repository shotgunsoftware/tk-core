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
        super().setUp()
        self.util_filesystem_test_folder_location = os.path.join(
            self.fixtures_root, "util", "filesystem"
        )

    def test_safe_delete_non_existing_folder(self):
        """
        Check that a non-existing folder deletion fails
        """
        dst_folder = os.path.join(self.tank_temp, "non_existing_folder")
        self.assertFalse(os.path.exists(dst_folder))
        fs.safe_delete_folder(dst_folder)
        self.assertFalse(os.path.exists(dst_folder))

    def test_safe_delete_folder(self):
        """
        Check that the test folder and all its contents are deleted recursively
        """
        src_folder = os.path.join(
            self.util_filesystem_test_folder_location, "delete_folder"
        )
        dst_folder = os.path.join(self.tank_temp, "folder")
        shutil.copytree(src_folder, dst_folder)
        self.assertTrue(os.path.exists(dst_folder))
        fs.safe_delete_folder(dst_folder)
        self.assertFalse(os.path.exists(dst_folder))

    def test_safe_delete_folder_with_file_in_use(self):
        """
        Check that delete folder will delete as much as it can, even when
        it encounters errors like failures to delete some of the items in
        the folder
        """
        src_folder = os.path.join(
            self.util_filesystem_test_folder_location, "delete_folder"
        )
        dst_folder = os.path.join(self.tank_temp, "folder_in_use")
        shutil.copytree(src_folder, dst_folder)
        self.assertTrue(os.path.exists(dst_folder))
        # open a file in the directory to remove ...
        with open(os.path.join(dst_folder, "ReadWrite.txt")) as f:
            # ... and check that a failure occurs
            fs.safe_delete_folder(dst_folder)
            if is_windows():
                # A failure occurred, folder should still be there
                self.assertTrue(
                    os.path.exists(dst_folder)
                )  # on Windows removal of in-use files behaves differently than...
            else:
                self.assertFalse(
                    os.path.exists(dst_folder)
                )  # ... on Unix, see comments for https://docs.python.org/2/library/os.html#os.remove

    def test_safe_delete_folder_with_read_only_items(self):
        """
        Check that safe_delete_folder will delete all items in the folder, even read only ones
        """
        src_folder = os.path.join(
            self.util_filesystem_test_folder_location, "delete_folder"
        )
        dst_folder = os.path.join(self.tank_temp, "folder_with_read_only_items")
        shutil.copytree(src_folder, dst_folder)
        self.assertTrue(os.path.exists(dst_folder))

        # make folder items read-only
        read_only_filename = os.path.join(dst_folder, "ReadOnly.txt")
        file_permissions = os.stat(read_only_filename)[stat.ST_MODE]
        os.chmod(read_only_filename, file_permissions & ~stat.S_IWRITE)
        if is_windows():
            folder_permissions = os.stat(dst_folder)[stat.ST_MODE]
            os.chmod(dst_folder, folder_permissions & ~stat.S_IWRITE)

        fs.safe_delete_folder(dst_folder)

        # check that the folder is deleted successfully
        self.assertFalse(os.path.exists(dst_folder))

    def test_unused_path(self):
        """
        Test the get_unused_path helper
        """
        test_folder = os.path.join(self.tank_temp, "unused_tests")

        # Basic test with a simple name
        path = os.path.join(test_folder, "foo")
        self.assertEqual(fs.get_unused_path(path), path)
        # Create the target path and check it is detected
        fs.ensure_folder_exists(path)
        self.assertEqual(fs.get_unused_path(path), "%s_1" % path)

        # Test we insert the number in the right place if we have some "." in the
        # base path.
        path = os.path.join(test_folder, "foo.0020.exr")
        self.assertEqual(fs.get_unused_path(path), path)
        fs.touch_file(path)
        self.assertEqual(
            fs.get_unused_path(path), os.path.join(test_folder, "foo_1.0020.exr")
        )

        # Test multiple iterations
        fs.touch_file(os.path.join(test_folder, "foo_1.0020.exr"))
        fs.touch_file(os.path.join(test_folder, "foo_2.0020.exr"))
        fs.touch_file(os.path.join(test_folder, "foo_3.0020.exr"))
        fs.touch_file(os.path.join(test_folder, "foo_4.0020.exr"))
        self.assertEqual(
            fs.get_unused_path(path), os.path.join(test_folder, "foo_5.0020.exr")
        )

        # Clean up
        fs.safe_delete_folder(test_folder)

    def test_copy_file(self):
        """
        Test the copy_file helper
        """
        # A root folder
        copy_test_root_folder = os.path.join(self.tank_temp, "copy_tests")
        fs.ensure_folder_exists(copy_test_root_folder, permissions=0o777)
        # Copy src file
        copy_test_basename = "copy_file.txt"
        copy_test_file = os.path.join(copy_test_root_folder, copy_test_basename)
        fs.touch_file(copy_test_file, permissions=0o777)
        # Copy dst folder
        copy_test_dst_folder = os.path.join(
            copy_test_root_folder, "copy_test_dst_folder"
        )
        fs.ensure_folder_exists(copy_test_dst_folder, permissions=0o777)
        # Copy dst file
        copy_test_dst_file = os.path.join(copy_test_dst_folder, "copied_file.txt")

        # Tests
        # Test folder name dst argument
        fs.copy_file(
            os.path.join(copy_test_root_folder, copy_test_basename),
            copy_test_dst_folder,
            permissions=0o777,
        )
        self.assertTrue(
            os.path.exists(os.path.join(copy_test_dst_folder, copy_test_basename))
        )
        # Test file name dst argument
        fs.copy_file(
            os.path.join(copy_test_root_folder, copy_test_basename), copy_test_dst_file
        )
        self.assertTrue(os.path.exists(copy_test_dst_file))

        # Clean up
        fs.safe_delete_folder(copy_test_root_folder)

    def test_copy_folder(self):
        """
        Test the copy_folder helper
        """
        # A root folder
        copy_test_root_folder = os.path.join(self.tank_temp, "copy_tests")
        fs.ensure_folder_exists(copy_test_root_folder, permissions=0o777)
        # Source folder
        copy_test_src_folder = os.path.join(copy_test_root_folder, "copy_test_src_folder")
        fs.ensure_folder_exists(copy_test_src_folder, permissions=0o777)
        # Copy src file
        copy_test_basename = "copy_file.txt"
        copy_test_file = os.path.join(copy_test_src_folder, copy_test_basename)
        fs.touch_file(copy_test_file, permissions=0o777)
        # Copy dst folder
        copy_test_dst_folder = os.path.join(
            copy_test_root_folder, "copy_test_dst_folder"
        )

        # Tests
        # Test folder with SKIP_LIST_DEFAULT
        skip_list_copy = fs.SKIP_LIST_DEFAULT.copy()
        fs.copy_folder(
            copy_test_src_folder,
            copy_test_dst_folder,
        )
        self.assertTrue(os.path.exists(copy_test_dst_folder))
        self.assertTrue(
            os.path.exists(os.path.join(copy_test_dst_folder, copy_test_basename))
        )
        self.assertEqual(fs.SKIP_LIST_DEFAULT, skip_list_copy)

        # Clean up this test
        fs.safe_delete_folder(copy_test_dst_folder)

        # Test folder with custom skip list
        skip_list = [".vscode"]
        skip_list_copy = skip_list.copy()
        fs.copy_folder(
            copy_test_src_folder,
            copy_test_dst_folder,
            skip_list=skip_list,
        )
        self.assertTrue(os.path.exists(copy_test_dst_folder))
        self.assertTrue(
            os.path.exists(os.path.join(copy_test_dst_folder, copy_test_basename))
        )
        self.assertEqual(skip_list, skip_list_copy)

        # Clean up everything
        fs.safe_delete_folder(copy_test_root_folder)


class TestOpenInFileBrowser(TankTestBase):
    """
    Tests the open_file_browser functionality
    """

    def setUp(self):
        super().setUp()
        self.test_folder = os.path.join(self.tank_temp, "foo")
        self.test_file = os.path.join(self.test_folder, "bar.txt")
        self.test_sequence = os.path.join(self.test_folder, "render.%04d.exr")
        if not os.path.exists(self.test_folder):
            os.mkdir(self.test_folder)
        if not os.path.exists(self.test_file):
            with open(self.test_file, "wt") as fh:
                fh.write("hello test file!\n")

    def test_bad_path(self):
        """
        Tests opening a folder via the open_file_browser method.
        """
        self.assertRaises(ValueError, fs.open_file_browser, "/some/bad/bad_path")
        self.assertRaises(ValueError, fs.open_file_browser, "X:\\some\\bad\\bad_path")
        self.assertRaises(ValueError, fs.open_file_browser, "bad_path")
        self.assertRaises(ValueError, fs.open_file_browser, "")

    @mock.patch("subprocess.call", return_value=0)
    def test_folder(self, subprocess_mock):
        """
        Tests opening a folder
        """
        fs.open_file_browser(self.test_folder)
        args, kwargs = subprocess_mock.call_args

        if is_linux():
            self.assertEqual(args[0], ["xdg-open", self.test_folder])

        elif is_macos():
            self.assertEqual(args[0], ["open", self.test_folder])

        elif is_windows():
            self.assertEqual(args[0], ["cmd.exe", "/C", "start", self.test_folder])

    @mock.patch("subprocess.call", return_value=1234)
    def test_failed_folder(self, _):
        """
        Test failing opening folder
        """
        self.assertRaises(RuntimeError, fs.open_file_browser, self.test_folder)

    @mock.patch("subprocess.call", return_value=0)
    def test_file(self, subprocess_mock):
        """
        Tests opening a file
        """
        fs.open_file_browser(self.test_file)
        args, kwargs = subprocess_mock.call_args

        if is_linux():
            self.assertEqual(args[0], ["xdg-open", os.path.dirname(self.test_file)])

        elif is_macos():
            self.assertEqual(args[0], ["open", "-R", self.test_file])

        elif is_windows():
            self.assertEqual(args[0], ["explorer", "/select,", self.test_file])

    @mock.patch("subprocess.call", return_value=1234)
    def test_failed_file(self, _):
        """
        Test failing opening folder on mac/linux
        """
        if not is_windows():
            self.assertRaises(RuntimeError, fs.open_file_browser, self.test_file)

    @mock.patch("subprocess.call", return_value=0)
    def test_sequence(self, subprocess_mock):
        """
        Tests opening a folder
        """
        fs.open_file_browser(self.test_sequence)
        args, kwargs = subprocess_mock.call_args

        if is_linux():
            self.assertEqual(args[0], ["xdg-open", os.path.dirname(self.test_sequence)])

        elif is_macos():
            self.assertEqual(args[0], ["open", os.path.dirname(self.test_sequence)])

        elif is_windows():
            self.assertEqual(
                args[0], ["cmd.exe", "/C", "start", os.path.dirname(self.test_sequence)]
            )
