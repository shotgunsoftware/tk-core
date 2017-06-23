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
from tank_test.tank_test_base import *
import tank.util.filesystem as fs
import shutil
import stat
import sys


class TestFileSystem(TankTestBase):
    
    def setUp(self):
        super(TestFileSystem, self).setUp()
        self.util_filesystem_test_folder_location = os.path.join(self.fixtures_root, "util", "filesystem")

    def test_delete_non_existing_folder(self):
        """
        Check that a non-existing folder deletion fails
        """
        dst_folder = os.path.join(self.tank_temp, "non_existing_folder")
        self.assertFalse(os.path.exists(dst_folder))
        self.assertFalse(fs.delete_folder(dst_folder))

    def test_delete_folder(self):
        """
        Check that the test folder and all its contents are deleted recursively
        """
        src_folder = os.path.join(self.util_filesystem_test_folder_location, "delete_folder")
        dst_folder = os.path.join(self.tank_temp, "folder")
        shutil.copytree(src_folder, dst_folder)
        self.assertTrue(os.path.exists(dst_folder))
        self.assertTrue(fs.delete_folder(dst_folder))
        self.assertFalse(os.path.exists(dst_folder))

    def test_delete_folder_with_file_in_use(self):
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
            noErrors = fs.delete_folder(dst_folder)
            self.assertTrue(noErrors)
            if sys.platform == "win32":                
                # A failure occurred, folder should still be there
                self.assertTrue(os.path.exists(dst_folder)) # on Windows removal of in-use files behaves differently than...
            else:
                self.assertFalse(os.path.exists(dst_folder)) # ... on Unix, see comments for https://docs.python.org/2/library/os.html#os.remove

    def test_delete_folder_with_read_only_items(self):
        """
        Check that delete_folder will delete all items in the folder, even read only ones
        """
        src_folder = os.path.join(self.util_filesystem_test_folder_location, "delete_folder")
        dst_folder = os.path.join(self.tank_temp, "folder_with_read_only_items")
        shutil.copytree(src_folder, dst_folder)
        self.assertTrue(os.path.exists(dst_folder))

        # make folder items read-only
        os.chmod(os.path.join(dst_folder, "ReadOnly.txt"), stat.S_IREAD)
        os.chmod(dst_folder, stat.S_IREAD)

        noErrors = fs.delete_folder(dst_folder)

        # check that the folder is deleted successfully
        self.assertTrue(noErrors)
        self.assertFalse(os.path.exists(dst_folder))
