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
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """

        super().setUp()

        project_name = os.path.basename(self.project_root)
        # older publish to test we get the latest
        self.pub_1 = {
            "type": "PublishedFile",
            "id": 1,
            "code": "hello",
            "path_cache": "%s/foo/bar" % project_name,
            "created_at": datetime.datetime(2012, 10, 12, 12, 1),
            "path_cache_storage": self.primary_storage,
        }

        # publish matching older publish
        self.pub_2 = {
            "type": "PublishedFile",
            "id": 2,
            "code": "more recent",
            "path_cache": "%s/foo/bar" % project_name,
            "created_at": datetime.datetime(2012, 10, 13, 12, 1),
            "path_cache_storage": self.primary_storage,
        }

        self.pub_3 = {
            "type": "PublishedFile",
            "id": 3,
            "code": "world",
            "path_cache": "%s/foo/baz" % project_name,
            "created_at": datetime.datetime(2012, 10, 13, 12, 2),
            "path_cache_storage": self.primary_storage,
        }

        # sequence publish
        self.pub_4 = {
            "type": "PublishedFile",
            "id": 4,
            "code": "sequence_file",
            "path_cache": "%s/foo/seq_%%03d.ext" % project_name,
            "created_at": datetime.datetime(2012, 10, 13, 12, 2),
            "path_cache_storage": self.primary_storage,
        }

        # Create another project and add it to the mock database to test
        # finding publishes across multiple projects.
        self.proj_2, self.proj_2_root = self.create_project({"name": "second project"})
        self.proj_2_name = os.path.basename(self.proj_2_root)

        # Add publishes to the project that was just created.
        self.proj_2_pub_1 = {
            "type": "PublishedFile",
            "code": "hello",
            "path_cache": "%s/foo/bar" % self.proj_2_name,
            "created_at": datetime.datetime(2012, 10, 12, 12, 1),
            "path_cache_storage": self.primary_storage,
        }

        # publish matching older publish
        self.proj_2_pub_2 = {
            "type": "PublishedFile",
            "code": "more recent",
            "path_cache": "%s/foo/bar" % self.proj_2_name,
            "created_at": datetime.datetime(2012, 10, 13, 12, 1),
            "path_cache_storage": self.primary_storage,
        }

        # Add all the publishes to mocked shotgun
        self.add_to_sg_mock_db(
            [
                self.pub_1,
                self.pub_2,
                self.pub_3,
                self.pub_4,
                self.proj_2_pub_1,
                self.proj_2_pub_2,
            ]
        )

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
        super().setUp()
        self.setup_multi_root_fixtures()

    def test_multi_root(self):
        pass
    def test_storage_misdirection(self):
        pass
    def test_multi_root_not_only_current_project(self):
        pass
class TestShotgunDownloadUrl(ShotgunTestBase):
    def setUp(self):
        super().setUp()

        # Identify the source file to "download"
        self.download_source = os.path.join(
            self.fixtures_root, "config", "hooks", "toolkitty.png"
        )

        # Construct a URL from the source file name
        # "file" will be used for the protocol, so this URL will look like
        # `file:///fixtures_root/config/hooks/toolkitty.png`
        if sys.platform == "win32":
            self.download_url = "file:///{p}".format(
                p = self.download_source.replace("\\", "/")
            )
        else:
            self.download_url = urllib.parse.urlunparse(
                ("file", None, self.download_source, None, None, None)
            )

        # Temporary destination to "download" source file to.
        self.download_destination = os.path.join(
            self.tank_temp,
            self.short_test_name,
            "config",
            "foo",
            "test_shotgun_download_url.png",
        )
        os.makedirs(os.path.dirname(self.download_destination))
        if os.path.exists(self.download_destination):
            os.remove(self.download_destination)

        # Make sure mockgun is properly configured
        if self.mockgun.config.server is None:
            self.mockgun.config.server = "unit_test_mock_sg"

    def tearDown(self):
        if os.path.exists(self.download_destination):
            os.remove(self.download_destination)

        # important to call base class so it can clean up memory
        super().tearDown()

    def test_download(self):
        pass
    def test_use_url_extension(self):
        pass
class TestShotgunDownloadAndUnpack(ShotgunTestBase):
    """
    Test the two exposed functions that use the _download_and_unpack() work function.
    """

    def setUp(self):
        super().setUp()

        zip_file_location = os.path.join(self.fixtures_root, "misc", "zip")
        # Identify the source file to "download"
        self.download_source = os.path.join(zip_file_location, "tank_core.zip")
        # store the expected contents of the zip, to ensure it's properly
        # extracted.
        self.expected_output_txt = os.path.join(zip_file_location, "tank_core.txt")
        self.expected_output = open(self.expected_output_txt).read().split("\n")

        # Construct URLs from the source file name
        # "file" will be used for the protocol, so this URL will look like
        # `file:///fixtures_root/misc/zip/tank_core.zip`
        self.good_zip_url = urllib.parse.urlunparse(
            ("file", None, self.download_source, None, None, None)
        )
        self.bad_zip_url = urllib.parse.urlunparse(
            ("file", None, self.download_source, None, None, None)
        )

        # Temporary destination to unpack sources to.
        self.download_destination = os.path.join(
            self.tank_temp, self.short_test_name, "test_unpack"
        )
        os.makedirs(os.path.dirname(self.download_destination))
        if os.path.exists(self.download_destination):
            os.remove(self.download_destination)

        # Make sure mockgun is properly configured
        if self.mockgun.config.server is None:
            self.mockgun.config.server = "unit_test_mock_sg"

    def test_download_and_unpack_attachment(self):
        pass
    def test_download_and_unpack_url(self):
        pass
    def test_no_source(self):
        pass
