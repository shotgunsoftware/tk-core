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
import sgtk

from tank_test.tank_test_base import *
from tank.errors import TankError
from tank.descriptor.errors import TankDescriptorError

class TestDescriptorSupport(TankTestBase):

    def setUp(self, parameters=None):

        super(TestDescriptorSupport, self).setUp()

        self.install_root = os.path.join(
            self.tk.pipeline_configuration.get_install_location(),
            "install"
        )

    def _create_info_yaml(self, path):
        """
        create a mock info.yml
        """
        sgtk.util.filesystem.ensure_folder_exists(path)
        fh = open(os.path.join(path, "info.yml"), "wt")
        fh.write("foo")
        fh.close()

    def test_shotgun_descriptor_location(self):
        """
        Tests input validation for shotgun descriptor
        """
        location = {
            "type": "shotgun",
            "entity_type": "PipelineConfiguration",
            "name": "primary",
            "project_id": 123,
            "field": "sg_config",
            "version": 456
        }

        location_str = "sgtk:descriptor:shotgun?name=primary&entity_type=PipelineConfiguration&field=sg_config&version=456&project_id=123"

        faulty_location_1 = {
            "type": "shotgun",
            "entity_type": "PipelineConfiguration",
            "name": "primary",
            "project_id": "foo",
            "field": "sg_config",
            "version": 456
        }

        faulty_location_2 = {
            "type": "shotgun",
            "entity_type": "PipelineConfiguration",
            "name": "primary",
            "project_id": 123,
            "field": "sg_config",
            "version": "bar"
        }

        path = os.path.join(self.install_root, "sg", "unit_test_mock_sg", "PipelineConfiguration.sg_config", "p123_primary", "v456")
        self._create_info_yaml(path)

        d = self.tk.pipeline_configuration.get_app_descriptor(location)
        self.assertEqual(d.get_path(), path)

        d = self.tk.pipeline_configuration.get_app_descriptor(location_str)
        self.assertEqual(d.get_path(), path)

        self.assertRaises(
            sgtk.descriptor.TankDescriptorError,
            self.tk.pipeline_configuration.get_app_descriptor,
            faulty_location_1
        )

        self.assertRaises(
            sgtk.descriptor.TankDescriptorError,
            self.tk.pipeline_configuration.get_app_descriptor,
            faulty_location_2
        )

    def test_app_store_descriptor_location(self):
        """
        Tests an appstore descriptor bundle path for the given bundle type and location.
        """

        location = {"type": "app_store", "version": "v0.1.2", "name": "tk-bundle"}
        path = os.path.join(self.install_root, "app_store", "tk-bundle", "v0.1.2")
        self._create_info_yaml(path)

        d = self.tk.pipeline_configuration.get_app_descriptor(location)
        self.assertEqual(d.get_path(), path)

        d = self.tk.pipeline_configuration.get_engine_descriptor(location)
        self.assertEqual(d.get_path(), path)

        d = self.tk.pipeline_configuration.get_framework_descriptor(location)
        self.assertEqual(d.get_path(), path)


    def test_manual_descriptor_location(self):
        """
        Tests a manual descriptor bundle path for the given bundle type and location.
        """

        location = {"type": "manual", "version": "v0.1.2", "name": "tk-bundle"}
        path = os.path.join(self.install_root, "manual", "tk-bundle", "v0.1.2")
        self._create_info_yaml(path)

        d = self.tk.pipeline_configuration.get_app_descriptor(location)
        self.assertEqual(d.get_path(), path)

        d = self.tk.pipeline_configuration.get_engine_descriptor(location)
        self.assertEqual(d.get_path(), path)

        d = self.tk.pipeline_configuration.get_framework_descriptor(location)
        self.assertEqual(d.get_path(), path)


    def test_dev_descriptor_location(self):
        """
        Tests a dev descriptor bundle path
        """
        path = os.path.join(self.tk.pipeline_configuration.get_path(), "bundle")
        self._create_info_yaml(path)

        d = self.tk.pipeline_configuration.get_app_descriptor({"type": "dev", "path": "{PIPELINE_CONFIG}/bundle"})
        self.assertEqual(d.get_path(), path)

        d = self.tk.pipeline_configuration.get_app_descriptor({"type": "dev", "path": path})
        self.assertEqual(d.get_path(), path)


    def _test_git_descriptor_location_with_repo(self, repo):
        """
        Tests a git descriptor bundle path for the given bundle type and location and a given
        repo.
        """
        path = os.path.join(self.install_root, "git", os.path.basename(repo), "v0.1.2")
        self._create_info_yaml(path)

        d = self.tk.pipeline_configuration.get_app_descriptor({"type": "git", "path": repo, "version": "v0.1.2"})
        self.assertEqual(d.get_path(), path)

    def test_git_descriptor_location(self):
        """
        Tests a git descriptor bundle path for the given bundle type and location for all
        supported repo naming convention.

        :param bundle_type: One of descriptor.AppDescriptor.{APP,ENGINE,FRAMEWORK}
        :param bundle_location: Location in the pipeline configuration where bundles of the given
            type get installed.
        """
        for uri in [
            "git@github.com:manneohrstrom/tk-hiero-publish.git",
            "https://github.com/manneohrstrom/tk-hiero-publish.git",
            "git://github.com/manneohrstrom/tk-hiero-publish.git",
            "/full/path/to/local/repo.git"
        ]:
            self._test_git_descriptor_location_with_repo(uri)


    def test_git_version_logic(self):
        """
        Test git descriptor version logic
        """
        desc = self.tk.pipeline_configuration.get_app_descriptor(
                {"type": "git", "path": "git@github.com:dummy/tk-multi-dummy.git", "version": "v1.2.3"}
        )

        v1 = ["v1.2.3"]
        v2 = ["v1.2.3", "v1.2.2"]
        v3 = ["v1.2.3", "v1.2.233", "v1.3.1", "v2.3.1"]
        v4 = ["v1.2.3", "v2.3.1.8", "v1.2.233", "v1.3.1", "v2.3.1", "v1.2.233.34"]
        v5 = ["v1.2.3", "v1.2.233", "v1.4.233", "v1.3.1.2.3"]

        # no input
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern([], None), None)
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern([], "vx.x.x"), None)

        # just latest version
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v1, None), "v1.2.3")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v2, None), "v1.2.3")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v3, None), "v2.3.1")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v4, None), "v2.3.1.8")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v5, None), "v1.4.233")

        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v1, "vx.x.x"), "v1.2.3")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v2, "vx.x.x"), "v1.2.3")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v3, "vx.x.x"), "v2.3.1")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v4, "vx.x.x"), "v2.3.1.8")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v5, "vx.x.x"), "v1.4.233")

        # absolute match
        for vv in [v1, v2, v3, v4, v5]:
            self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(vv, "v1.2.3"), "v1.2.3")

        # simple matches
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v1, "v1.2.x"), "v1.2.3")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v2, "v1.2.x"), "v1.2.3")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v3, "v1.2.x"), "v1.2.233")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v4, "v1.2.x"), "v1.2.233.34")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v5, "v1.2.x"), "v1.2.233")

        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(["v1.2.3", "v1.2.233", "v1.3.1"], "v1.3.x"), "v1.3.1")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(["v1.2.3", "v1.2.233", "v1.3.1", "v2.3.1"], "v1.x.x"), "v1.3.1")

        # forks
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(["v1.2.3", "v1.2.233", "v1.3.1.2.3"], "v1.3.x"), "v1.3.1.2.3")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(["v1.2.3", "v1.2.233", "v1.3.1.2.3", "v1.4.233"], "v1.3.1.x"), "v1.3.1.2.3")

        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(["v1.2.3", "v1.2.233", "v1.5.1"], "v1.3.x"), None)
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(["v1.2.3", "v1.2.233", "v1.5.1"], "v2.x.x"), None)
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(["v1.2.3", "v1.2.233", "v5.5.1"], "v2.x.x"), None)

        # invalids
        self.assertRaisesRegexp(TankError,
                                "Incorrect version pattern '.*'. There should be no string after a 'x'",
                                desc._io_descriptor._find_latest_tag_by_pattern,
                                ["v1.2.3", "v1.2.233", "v1.3.1"],
                                "v1.x.2")

    def test_pattern_version_logic(self):
        """
        Test pattern and descriptor version logic
        """
        desc = self.tk.pipeline_configuration.get_app_descriptor({
            "type": "git",
            "path": "git@github.com:dummy/tk-multi-dummy.git",
            "version": "v0.0.0"
        })
        # Test regular releases
        releases = [
            "v1.0.1",
            "v1.0.2",
            "v1.0.10",
        ]
        # Ensure un-supported patterns raise errors
        self.assertRaises(
            TankDescriptorError,
            desc._io_descriptor._find_latest_tag_by_pattern, releases, "x.x.x",
        )
        self.assertRaises(
            TankDescriptorError,
            desc._io_descriptor._find_latest_tag_by_pattern, releases, "v1.x",
        )
        self.assertRaises(
            TankDescriptorError,
            desc._io_descriptor._find_latest_tag_by_pattern, releases, "vx.x-x",
        )
        self.assertRaises(
            TankDescriptorError,
            desc._io_descriptor._find_latest_tag_by_pattern, releases, "vx.x.x-rc",
        )
        # Test releases with various number of tokens
        releases = [
            "v1.0",
            "v1.0.2",
            "v1.0.10",
            "v2.0.3",
            "v2.0.3-rc.1",
            "v2.0.3-rc.2",
            "v2.1.0",
        ]
        self.assertEqual(
            desc._io_descriptor._find_latest_tag_by_pattern(releases, "v1.x.x"),
            "v1.0.10"
        )
        self.assertEqual(
            desc._io_descriptor._find_latest_tag_by_pattern(releases, "v2.x.x"),
            "v2.1.0"
        )
        self.assertEqual(
            desc._io_descriptor._find_latest_tag_by_pattern(releases, "vx.x.x"),
            "v2.1.0"
        )
        self.assertEqual(
            desc._io_descriptor._find_latest_tag_by_pattern(releases, "v2.x.x.x"),
            "v2.0.3-rc.2"
        )
        self.assertEqual(
            desc._io_descriptor._find_latest_tag_by_pattern(releases, "v2.0.3-rc.x"),
            "v2.0.3-rc.2"
        )
        self.assertIsNone(
            desc._io_descriptor._find_latest_tag_by_pattern(releases, "v2.x.x.x.x.x.x.x"),
        )
        # Test topic releases where a ticket number is used as a topic.
        topic_releases = [
            "v1.0.2-123546_my_topic",
            "v1.0.2-123546_my_topic.1",
            "v1.0.2-123546_my_topic.1.1",
            "v1.0.2-123546_my_topic.1.2",
            "v1.0.2-123546_my_topic.2",
        ]
        self.assertEqual(
            desc._io_descriptor._find_latest_tag_by_pattern(topic_releases, "vx.x.x-x"),
            "v1.0.2-123546_my_topic.2"
        )
        self.assertEqual(
            desc._io_descriptor._find_latest_tag_by_pattern(topic_releases, "v1.0.2-123546_my_topic.x.x"),
            "v1.0.2-123546_my_topic.1.2"
        )
        # Tests releases where an external software release is used as topic
        releases = [
            "v1.0.1-maya2015",
            "v1.0.1-maya2015.rc.2",
            "v1.0.1-maya2015.rc.10",
            "v2.0.0-maya2015",
            "v1.0.1-maya2017",
            "v1.0.1-maya2017.rc.2",
            "v1.0.1-maya2017.rc.10",
            "v2.0.0-maya2017",
        ]
        self.assertEqual(
            desc._io_descriptor._find_latest_tag_by_pattern(releases, "v1.0.1-maya2015"),
            "v1.0.1-maya2015.rc.10"
        )
        self.assertEqual(
            desc._io_descriptor._find_latest_tag_by_pattern(releases, "v1.0.1-maya2015.rc"),
            "v1.0.1-maya2015.rc.10"
        )
        self.assertEqual(
            desc._io_descriptor._find_latest_tag_by_pattern(releases, "v2.0.0-maya2017"),
            "v2.0.0-maya2017"
        )

