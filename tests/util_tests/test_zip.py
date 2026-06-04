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
from tank_test.tank_test_base import ShotgunTestBase, setUpModule  # noqa
import tank


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
        pass
    def test_single_folder_unzip(self):
        pass
    def test_single_file_unzip(self):
        pass
