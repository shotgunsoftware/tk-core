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

from tank_test.tank_test_base import *
from tank.errors import TankError


class TestDescriptors(TankTestBase):


    def test_app_store_descriptor_location(self):
        """
        Tests an appstore descriptor bundle path for the given bundle type and location.
        """
        install_root = os.path.join(self.tk.pipeline_configuration.get_install_location(), "install")
        location = {"type": "app_store", "version": "v0.1.2", "name": "tk-bundle"}
        path = os.path.join(install_root, "app_store", "tk-bundle", "v0.1.2")

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

        install_root = os.path.join(self.tk.pipeline_configuration.get_install_location(), "install")
        location = {"type": "manual", "version": "v0.1.2", "name": "tk-bundle"}
        path = os.path.join(install_root, "manual", "tk-bundle", "v0.1.2")

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

        d = self.tk.pipeline_configuration.get_app_descriptor({"type": "dev", "path": "{PIPELINE_CONFIG}/bundle"})
        self.assertEqual(d.get_path(), os.path.join(self.tk.pipeline_configuration.get_path(), "bundle"))

        d = self.tk.pipeline_configuration.get_app_descriptor({"type": "dev", "path": "path/to/bundle"})
        self.assertEqual(d.get_path(), os.path.join("path", "to", "bundle"))


    def _test_git_descriptor_location_with_repo(self, repo):
        """
        Tests a git descriptor bundle path for the given bundle type and location and a given
        repo.
        """
        install_root = os.path.join(self.tk.pipeline_configuration.get_install_location(), "install")

        d = self.tk.pipeline_configuration.get_app_descriptor({"type": "git", "path": repo, "version": "v0.1.2"})
        self.assertEqual(d.get_path(), os.path.join(install_root , "git", os.path.basename(repo), "v0.1.2"))

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

        # absolute match
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(["v1.2.3"], "v1.2.3"), "v1.2.3")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(["v1.2.3", "v1.2.2"], "v1.2.3"), "v1.2.3")

        # simple matches
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(["v1.2.3", "v1.2.2"], "v1.2.x"), "v1.2.3")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(["v1.2.3", "v1.2.2"], "v1.2.x"), "v1.2.3")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(["v1.2.3", "v1.2.233", "v1.3.1"], "v1.3.x"), "v1.3.1")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(["v1.2.3", "v1.2.233", "v1.3.1", "v2.3.1"], "v1.x.x"), "v1.3.1")

        # forks
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(["v1.2.3", "v1.2.233", "v1.3.1.2.3"], "v1.3.x"), "v1.3.1.2.3")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(["v1.2.3", "v1.2.233", "v1.3.1.2.3", "v1.4.233"], "v1.3.1.x"), "v1.3.1.2.3")

        # invalids
        self.assertRaisesRegexp(TankError,
                                "Incorrect version pattern '.*'. There should be no digit after a 'x'",
                                desc._io_descriptor._find_latest_tag_by_pattern,
                                ["v1.2.3", "v1.2.233", "v1.3.1"],
                                "v1.x.2")
