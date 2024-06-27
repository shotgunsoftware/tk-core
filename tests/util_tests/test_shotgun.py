# Copyright (c) 2013 Shotgun Software Inc.
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
import shutil
import datetime
import urllib

import tank
from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    TankTestBase,
    ShotgunTestBase,
)

from tank.template import TemplatePath
from tank.templatekey import SequenceKey


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

        super(TestShotgunFindPublish, self).setUp()

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
        paths = [os.path.join(self.project_root, "foo", "bar")]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), len(paths))
        self.assertEqual(set(d.keys()), set(paths))
        # make sure we got the latest matching publish
        sg_data = d.get(paths[0])
        self.assertEqual(sg_data["id"], self.pub_2["id"])
        self.assertEqual(sg_data["type"], "PublishedFile")
        # make sure we are only getting the ID back.
        self.assertEqual(set(sg_data.keys()), set(("type", "id")))

    def test_most_recent_path(self):
        # check that dupes return the more recent record
        paths = [os.path.join(self.project_root, "foo", "bar")]
        d = tank.util.find_publish(self.tk, paths, fields=["code"])
        self.assertEqual(len(d), 1)
        sg_data = d.get(paths[0])
        self.assertEqual(sg_data["code"], "more recent")

    def test_missing_paths(self):
        paths = [
            os.path.join(self.project_root, "foo", "bar"),
            os.path.join("tmp", "foo"),
        ]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), 1)
        self.assertEqual(set(d.keys()), set((paths[0],)))

    def test_sequence_path(self):
        # make sequence template matching sequence publish
        keys = {"seq": SequenceKey("seq", format_spec="03")}
        template = TemplatePath("foo/seq_{seq}.ext", keys, self.project_root)
        self.tk.templates["sequence_test"] = template
        paths = [os.path.join(self.project_root, "foo", "seq_002.ext")]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), 1)
        self.assertEqual(set(d.keys()), set((paths[0],)))
        sg_data = d.get(paths[0])
        self.assertEqual(sg_data["id"], self.pub_4["id"])

    def test_abstracted_sequence_path(self):
        # make sequence template matching sequence publish
        keys = {"seq": SequenceKey("seq", format_spec="03")}
        template = TemplatePath("foo/seq_{seq}.ext", keys, self.project_root)
        self.tk.templates["sequence_test"] = template
        paths = [os.path.join(self.project_root, "foo", "seq_%03d.ext")]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), 1)
        self.assertEqual(set(d.keys()), set((paths[0],)))
        sg_data = d.get(paths[0])
        self.assertEqual(sg_data["id"], self.pub_4["id"])

    def test_ignore_missing(self):
        """
        If a storage is not registered in shotgun, the path is ignored
        (previously it used to raise an error)
        """
        paths = [os.path.join(self.project_root, "foo", "doesnotexist")]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), 0)

    def test_translate_abstract_fields(self):
        # We should get back what we gave since there won't be a matching
        # template for this path.
        self.assertEqual(
            "/jbee/is/awesome.0001.jpg",
            tank.util.shotgun.publish_creation._translate_abstract_fields(
                self.tk, "/jbee/is/awesome.0001.jpg"
            ),
        )

        # Build a set of matching templates.
        keys = dict(
            seq=tank.templatekey.SequenceKey("seq", format_spec="03"),
            frame=SequenceKey("frame", format_spec="04"),
        )
        template = TemplatePath(
            "folder/name_{seq}.{frame}.ext", keys, self.project_root
        )
        dup_template = TemplatePath(
            "folder/name_{seq}.{frame}.ext", keys, self.project_root
        )

        self.tk.templates["translate_fields_test"] = template

        # We should get back a transformed path since there's a single
        # matching template.
        path = os.path.join(self.project_root, "folder", "name_001.9999.ext")
        t_path = os.path.join(self.project_root, "folder", "name_%03d.%04d.ext")

        self.assertEqual(
            t_path,
            tank.util.shotgun.publish_creation._translate_abstract_fields(
                self.tk, path
            ),
        )

        self.tk.templates["translate_fields_test_dup"] = dup_template

        # We should get back what we gave due to multiple matching templates.
        self.assertEqual(
            path,
            tank.util.shotgun.publish_creation._translate_abstract_fields(
                self.tk, path
            ),
        )

    def test_find_only_current_project(self):
        """
        Test find_publish when only_current_project param is True. Results
        should be the same as when no value is passed for the param.
        """
        project_path = os.path.join(self.project_root, "foo", "bar")
        proj_2_path = os.path.join(self.proj_2_root, "foo", "bar")
        input_paths = [project_path, proj_2_path]

        result = tank.util.find_publish(self.tk, input_paths)
        result2 = tank.util.find_publish(
            self.tk, input_paths, only_current_project=True
        )

        # make sure passing no value for param 'only_current_project' has the same
        # same result as passing only_current_project=True
        assert result == result2

        # publishes are found only from current project, so we expect the result
        # to be the same as in `test_find`
        expected = {project_path: self.pub_2}
        expected_paths = expected.keys()
        assert len(result) == len(expected_paths)
        assert set(result.keys()) == set(expected_paths)

        for path, publish in expected.items():
            # make sure we got the latest matching publish
            sg_data = result.get(path)
            assert sg_data["id"] == publish["id"]
            assert sg_data["type"] == publish["type"]
            # make sure we are only getting the ID back.
            assert set(sg_data.keys()) == set(("type", "id"))

    def test_find_not_only_current_project(self):
        """
        Test find_publish when only_current_project param is False. Publishes
        should be found not only in the current project.
        """
        project_path = os.path.join(self.project_root, "foo", "bar")
        proj_2_path = os.path.join(self.proj_2_root, "foo", "bar")
        input_paths = [project_path, proj_2_path]

        # Find publishes set only_current_project param to False
        result = tank.util.find_publish(
            self.tk, input_paths, only_current_project=False
        )

        # We expect to find both paths from the two different projects
        expected = {project_path: self.pub_2, proj_2_path: self.proj_2_pub_2}
        expected_paths = expected.keys()

        # make sure we found both publishes from two different projects
        assert len(result) == len(expected_paths)
        assert set(result.keys()) == set(expected_paths)

        for path, publish in expected.items():
            # make sure we got the latest matching publish
            sg_data = result.get(path)
            assert sg_data["id"] == publish["id"]
            assert sg_data["type"] == publish["type"]
            # make sure we are only getting the ID and type back.
            assert set(sg_data.keys()) == set(("type", "id"))

    def test_find_only_current_project_multiple_pipeline_configs(self):
        """
        Test find_publish when only_current_project param is True, and there
        are multiple pipeline configurations. We should only find publishes
        from the current project of the pipeline configuration that is used.
        """
        # Create a new project and pipeline configuration, and set the new project
        # as the current project of the new pipeline configuraiton
        other_proj, other_proj_root = self.create_project({"name": "other project"})
        (_, _, _, _, other_tk,) = self.create_pipeline_configuration(other_proj)
        other_proj_name = os.path.basename(other_proj_root)
        other_pub = {
            "type": "PublishedFile",
            "code": "hello",
            "path_cache": "%s/new/path" % other_proj_name,
            "created_at": datetime.datetime(2021, 10, 12, 12, 1),
            "path_cache_storage": self.primary_storage,
        }
        self.add_to_sg_mock_db(other_pub)

        other_pub_path = os.path.join(other_proj_root, "new", "path")
        input_paths = [
            os.path.join(self.project_root, "foo", "bar"),
            os.path.join(self.proj_2_root, "foo", "bar"),
            other_pub_path,
        ]

        result = tank.util.find_publish(other_tk, input_paths)
        result2 = tank.util.find_publish(
            other_tk, input_paths, only_current_project=True
        )
        # assert results are the same to test default param only_current_project
        assert result == result2

        # expected to only find publishes in other_proj since we only looked in the current
        # project, and other_proj is the current project for the sgtk instance (other_tk)
        expected = {other_pub_path: other_pub}
        # make sure we found both publishes from two different projects
        expected_paths = expected.keys()
        assert len(result) == len(expected_paths)
        assert set(result.keys()) == set(expected_paths)
        # make sure we got the latest matching publish
        for path, publish in expected.items():
            sg_data = result.get(path)
            assert sg_data["id"] == publish["id"]
            assert sg_data["type"] == publish["type"]

    def test_find_not_only_current_project_multiple_pipeline_configs(self):
        """
        Test find_publish when only_current_project param is False, and there
        are multiple pipeline configurations. We should find publishes from
        all projects, no matter which pipeline configuration is used.
        """
        # Create a new project and pipelien configuration, and set the new project
        # as the current project for the new pipeline configuration.
        other_proj, other_proj_root = self.create_project({"name": "other project"})
        _, _, _, _, other_tk = self.create_pipeline_configuration(other_proj)
        other_proj_name = os.path.basename(other_proj_root)
        other_pub = {
            "type": "PublishedFile",
            "code": "hello",
            "path_cache": "%s/new/path" % other_proj_name,
            "created_at": datetime.datetime(2021, 10, 12, 12, 1),
            "path_cache_storage": self.primary_storage,
        }
        self.add_to_sg_mock_db(other_pub)

        proj_pub_path = os.path.join(self.project_root, "foo", "bar")
        proj_2_pub_path = os.path.join(self.proj_2_root, "foo", "bar")
        other_pub_path = os.path.join(other_proj_root, "new", "path")
        input_paths = [proj_pub_path, proj_2_pub_path, other_pub_path]

        result = tank.util.find_publish(
            self.tk, input_paths, only_current_project=False
        )
        result2 = tank.util.find_publish(
            other_tk, input_paths, only_current_project=False
        )
        # assert results are equal, since we are searching not only the current project
        assert result == result2
        # expect to find all publishes since we are looking at not only the current project
        expected = {
            proj_pub_path: self.pub_2,
            proj_2_pub_path: self.proj_2_pub_2,
            other_pub_path: other_pub,
        }
        # make sure we found both publishes from two different projects
        expected_paths = expected.keys()
        assert len(result) == len(expected_paths)
        assert set(result.keys()) == set(expected_paths)
        # make sure we got the latest matching publish
        for path, publish in expected.items():
            sg_data = result.get(path)
            assert set(sg_data.keys()) == set(("type", "id"))
            assert sg_data["id"] == publish["id"]
            assert sg_data["type"] == publish["type"]


class TestMultiRoot(TankTestBase):
    def setUp(self):
        super(TestMultiRoot, self).setUp()
        self.setup_multi_root_fixtures()

    def test_multi_root(self):
        project_name = os.path.basename(self.project_root)
        publish = {
            "type": "PublishedFile",
            "code": "other storage",
            "path_cache": "%s/foo/bar" % project_name,
            "created_at": datetime.datetime(2012, 10, 12, 12, 1),
            "path_cache_storage": self.alt_storage_1,
        }
        # Add these to mocked shotgun
        self.add_to_sg_mock_db([publish])
        paths = [os.path.join(self.alt_root_1, "foo", "bar")]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), 1)
        self.assertEqual(set(d.keys()), set(paths))
        # make sure we got the latest matching publish
        sg_data = d.get(paths[0])
        self.assertEqual(sg_data["id"], publish["id"])
        # make sure we are only getting the ID back.
        self.assertEqual(set(sg_data.keys()), set(("type", "id")))

    def test_storage_misdirection(self):
        project_name = os.path.basename(self.project_root)
        # define 2 publishes with the same path, different storages
        publish = {
            "type": "PublishedFile",
            "code": "storage misdirection",
            "path_cache": "%s/foo/bar" % project_name,
            "created_at": datetime.datetime(2012, 10, 12, 12, 1),
            "path_cache_storage": self.alt_storage_3,
        }
        publish2 = {
            "type": "PublishedFile",
            "code": "storage misdirection2",
            "path_cache": "%s/foo/bar" % project_name,
            "created_at": datetime.datetime(2012, 10, 12, 12, 1),
            "path_cache_storage": self.alt_storage_4,
        }
        self.add_to_sg_mock_db([publish, publish2])

        # querying root 3 path which is used by the "alternate_4" root in
        # roots.yml. the returned data should point to local storage 3 which
        # alt root 4 points to explicitly.
        paths = [os.path.join(self.alt_root_3, "foo", "bar")]
        pub_data = tank.util.find_publish(self.tk, paths, fields=["path_cache_storage"])
        self.assertEqual(len(pub_data), 1)
        self.assertEqual(set(pub_data.keys()), set(paths))
        self.assertEqual(
            pub_data[paths[0]]["path_cache_storage"]["id"], self.alt_storage_3["id"]
        )

        # querying root 4 path which is used by the "alternate_3" root in
        # roots.yml. the returned data should point to local storage 4 which
        # alt root 3 points to explicitly.
        paths = [os.path.join(self.alt_root_4, "foo", "bar")]
        pub_data = tank.util.find_publish(self.tk, paths, fields=["path_cache_storage"])
        self.assertEqual(len(pub_data), 1)
        self.assertEqual(set(pub_data.keys()), set(paths))
        self.assertEqual(
            pub_data[paths[0]]["path_cache_storage"]["id"], self.alt_storage_4["id"]
        )

    def test_multi_root_not_only_current_project(self):
        """
        Test finding publishes from not only the current project with multiple roots.
        """
        project_name = os.path.basename(self.project_root)
        proj_1_pub = {
            "type": "PublishedFile",
            "code": "another storage",
            "path_cache": "%s/a/project/path" % project_name,
            "created_at": datetime.datetime(2012, 10, 12, 12, 1),
            "path_cache_storage": self.alt_storage_1,
        }
        self.add_to_sg_mock_db([proj_1_pub])

        _, proj_2_root = self.create_project({"name": "second project"})
        proj_2_name = os.path.basename(proj_2_root)
        (proj_2_alt_root, proj_2_alt_storage) = self.create_storage_root(
            proj_2_name, "second_alternate_1"
        )
        proj_2_pub = {
            "type": "PublishedFile",
            "code": "other storage",
            "path_cache": "%s/another/project/path" % proj_2_name,
            "created_at": datetime.datetime(2021, 10, 12, 12, 1),
            "path_cache_storage": proj_2_alt_storage,
        }
        self.add_to_sg_mock_db([proj_2_pub])
        self.reload_pipeline_config()

        project_alternate_root = os.path.join(self.alt_root_1, "a", "project", "path")
        project_2_alternate_root = os.path.join(
            proj_2_alt_root, "another", "project", "path"
        )
        input_paths = [project_alternate_root, project_2_alternate_root]
        result = tank.util.find_publish(
            self.tk, input_paths, only_current_project=False
        )
        expected = {
            project_alternate_root: proj_1_pub,
            project_2_alternate_root: proj_2_pub,
        }
        expected_paths = input_paths
        assert len(result) == len(expected_paths)
        assert set(result.keys()) == set(expected_paths)

        for path, publish in expected.items():
            # make sure we got the latest matching publish
            sg_data = result.get(path)
            assert sg_data["id"] == publish["id"]
            assert sg_data["type"] == publish["type"]
            # make sure we are only getting the ID back.
            assert set(sg_data.keys()) == set(("type", "id"))


class TestShotgunDownloadUrl(ShotgunTestBase):
    def setUp(self):
        super(TestShotgunDownloadUrl, self).setUp()

        # Identify the source file to "download"
        self.download_source = os.path.join(
            self.fixtures_root, "config", "hooks", "toolkitty.png"
        )

        # Construct a URL from the source file name
        # "file" will be used for the protocol, so this URL will look like
        # `file:///fixtures_root/config/hooks/toolkitty.png`
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
        super(TestShotgunDownloadUrl, self).tearDown()

    def test_download(self):
        """
        Verify URL can be downloaded to specified path.
        """
        # Verify the download destination file does not exist.
        if os.path.exists(self.download_destination):
            os.remove(self.download_destination)
        self.assertFalse(os.path.exists(self.download_destination))

        # Attempt to download url and capture the downloaded file name.
        downloaded_to = tank.util.download_url(
            self.mockgun, self.download_url, self.download_destination
        )

        # Verify the destination file exists and is the same as
        # the return value from tank.util.download_url()
        self.assertTrue(os.path.exists(self.download_destination))
        self.assertEqual(self.download_destination, downloaded_to)

    def test_use_url_extension(self):
        """
        Verify correct exension gets extracted from the input
        url and appended to the input location value on return.
        """
        # Remove the file extension from the download destination
        path_base = os.path.splitext(self.download_destination)[0]

        # Ask tank.util.download_url() to append the exension from the
        # resolved URL to the input destination location and capture
        # the full path return value.
        full_path = tank.util.download_url(
            self.mockgun, self.download_url, path_base, True
        )

        # Verify the return value is different than the input value
        self.assertNotEqual(path_base, full_path)

        # Verify the correct file extension was returned.
        self.assertEqual(self.download_destination, full_path)


class TestShotgunDownloadAndUnpack(ShotgunTestBase):
    """
    Test the two exposed functions that use the _download_and_unpack() work function.
    """

    def setUp(self):
        super(TestShotgunDownloadAndUnpack, self).setUp()

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
        """
        Ensure download_and_unpack_attachment() retries after a failure,
        raises the appropriate Exception after repeated failures, calls
        download_attachment() as exepcted, and unpacks the
        returned zip file as expected.
        """
        download_result = open(self.download_source, "rb").read()
        target_dir = os.path.join(self.download_destination, "attachment")
        attachment_id = 764876347
        self.mockgun.download_attachment = mock.MagicMock()
        try:
            # fail forever, and ensure exception is raised.
            self.mockgun.download_attachment.side_effect = Exception("Test Exception")
            with self.assertRaises(tank.util.ShotgunAttachmentDownloadError):
                tank.util.shotgun.download_and_unpack_attachment(
                    self.mockgun, attachment_id, target_dir
                )

            # fail once, then succeed, ensuring retries work.
            self.mockgun.download_attachment.side_effect = (
                Exception("Test Exception"),
                download_result,
            )
            tank.util.shotgun.download_and_unpack_attachment(
                self.mockgun, attachment_id, target_dir
            )
            self.mockgun.download_attachment.assert_called_with(attachment_id)
            self.assertEqual(
                set(get_file_list(target_dir, target_dir)), set(self.expected_output)
            )
        finally:
            shutil.rmtree(target_dir)
            del self.mockgun.download_attachment

    def test_download_and_unpack_url(self):
        """
        Ensure download_and_unpack_url() raises the appropriate Exception after
        failure, and downloads and unpacks the specified URL as expected.
        """
        target_dir = os.path.join(self.download_destination, "url")
        try:
            with mock.patch("tank.util.shotgun.download.download_url") as download_url_mock:
                # Fail forever, and ensure exception is raised.
                download_url_mock.side_effect = Exception("Test Exception")
                with self.assertRaises(tank.util.ShotgunAttachmentDownloadError):
                    tank.util.shotgun.download_and_unpack_url(
                        self.mockgun, self.good_zip_url, target_dir
                    )

            # Download a zip file and ensure that it's unpacked to the expected location.
            tank.util.shotgun.download_and_unpack_url(
                self.mockgun, self.good_zip_url, target_dir
            )
            self.assertEqual(
                set(get_file_list(target_dir, target_dir)), set(self.expected_output)
            )
        finally:
            shutil.rmtree(target_dir)

    def test_no_source(self):
        """
        Ensure _download_and_unpack() raises the expected Exception when called with
        no source specified.
        """
        with self.assertRaises(ValueError):
            tank.util.shotgun.download._download_and_unpack(
                self.mockgun, self.download_destination, 5, True
            )
