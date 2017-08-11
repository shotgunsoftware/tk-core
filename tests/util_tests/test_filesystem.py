# Copyright (c) 2017 Shotgun Software Inc.
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
from tank_test.tank_test_base import TankTestBase
from tank_test.tank_test_base import setUpModule # noqa
import tank.util.filesystem as fs
import shutil
import stat
import sys


class TestFileSystem(TankTestBase):
    
    def setUp(self):
        super(TestFileSystem, self).setUp()
        self.util_filesystem_test_folder_location = os.path.join(self.fixtures_root, "util", "filesystem")

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
        src_folder = os.path.join(self.util_filesystem_test_folder_location, "delete_folder")
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
        src_folder = os.path.join(self.util_filesystem_test_folder_location, "delete_folder")
        dst_folder = os.path.join(self.tank_temp, "folder_in_use")
        shutil.copytree(src_folder, dst_folder)
        self.assertTrue(os.path.exists(dst_folder))
        # open a file in the directory to remove ...
        with open(os.path.join(dst_folder, "ReadWrite.txt")) as f:
            # ... and check that a failure occurs
            fs.safe_delete_folder(dst_folder)
            if sys.platform == "win32":                
                # A failure occurred, folder should still be there
                self.assertTrue(os.path.exists(dst_folder)) # on Windows removal of in-use files behaves differently than...
            else:
                self.assertFalse(os.path.exists(dst_folder)) # ... on Unix, see comments for https://docs.python.org/2/library/os.html#os.remove

    def test_safe_delete_folder_with_read_only_items(self):
        """
        Check that safe_delete_folder will delete all items in the folder, even read only ones
        """
        src_folder = os.path.join(self.util_filesystem_test_folder_location, "delete_folder")
        dst_folder = os.path.join(self.tank_temp, "folder_with_read_only_items")
        shutil.copytree(src_folder, dst_folder)
        self.assertTrue(os.path.exists(dst_folder))

        # make folder items read-only
        read_only_filename = os.path.join(dst_folder, "ReadOnly.txt")
        file_permissions = os.stat(read_only_filename)[stat.ST_MODE]
        os.chmod(read_only_filename, file_permissions & ~stat.S_IWRITE)
        if sys.platform == "win32":
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
        self.assertEqual(fs.get_unused_path(path), os.path.join(test_folder, "foo_1.0020.exr"))

        # Test multiple iterations
        fs.touch_file(os.path.join(test_folder, "foo_1.0020.exr"))
        fs.touch_file(os.path.join(test_folder, "foo_2.0020.exr"))
        fs.touch_file(os.path.join(test_folder, "foo_3.0020.exr"))
        fs.touch_file(os.path.join(test_folder, "foo_4.0020.exr"))
        self.assertEqual(fs.get_unused_path(path), os.path.join(test_folder, "foo_5.0020.exr"))

        # Clean up
        fs.safe_delete_folder(test_folder)
