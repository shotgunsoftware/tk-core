# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import datetime
import os
import shutil
import sys
import urllib.parse

import tank
from tank.template import TemplatePath
from tank.templatekey import SequenceKey
from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import ShotgunTestBase, TankTestBase, mock


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


class TestShotgunFindPublish(TankTestBase):
    def setUp(self):
        pass
    def test_find(self):
        pass
    def test_most_recent_path(self):
        pass
    def test_missing_paths(self):
        pass
    def test_sequence_path(self):
        pass
    def test_abstracted_sequence_path(self):
        pass
    def test_ignore_missing(self):
        pass
    def test_translate_abstract_fields(self):
        pass
    def test_find_only_current_project(self):
        pass
    def test_find_not_only_current_project(self):
        pass
    def test_find_only_current_project_multiple_pipeline_configs(self):
        pass
    def test_find_not_only_current_project_multiple_pipeline_configs(self):
        pass
class TestMultiRoot(TankTestBase):
    def setUp(self):
        pass
    def test_multi_root(self):
        pass
    def test_storage_misdirection(self):
        pass
    def test_multi_root_not_only_current_project(self):
        pass
class TestShotgunDownloadUrl(ShotgunTestBase):
    def setUp(self):
        pass
    def tearDown(self):
        pass
    def test_download(self):
        pass
    def test_use_url_extension(self):
        pass
class TestShotgunDownloadAndUnpack(ShotgunTestBase):
    """
    Test the two exposed functions that use the _download_and_unpack() work function.
    """

    def setUp(self):
        pass
    def test_download_and_unpack_attachment(self):
        pass
    def test_download_and_unpack_url(self):
        pass
    def test_no_source(self):
        pass
