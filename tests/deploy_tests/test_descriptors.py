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
from sgtk.deploy import descriptor
from tank.errors import TankError


class TestDescriptors(TankTestBase):

    def _test_app_store_descriptor_location(self, bundle_type, bundle_location):
        """
        Tests an app store descriptor bundle path for the given bundle type and location.

        :param bundle_type: One of descriptor.AppDescriptor.{APP,ENGINE,FRAMEWORK}
        :param bundle_location: Location in the pipeline configuration where bundles of the given
            type get installed.
        """

        desc = descriptor.get_from_location(
            bundle_type,
            self.tk.pipeline_configuration,
            {"type": "app_store", "version": "v0.1.2", "name": "tk-bundle"}
        )
        self.assertEqual(
            desc.get_path(),
            os.path.join(
                bundle_location,
                "app_store",
                "tk-bundle",
                "v0.1.2"
            )
        )

        # test caching
        desc2 = descriptor.get_from_location(
            bundle_type,
            self.tk.pipeline_configuration,
            {"type": "app_store", "version": "v0.1.2", "name": "tk-bundle"}
        )
        # note that we don't use the equality operator here but using 'is' to
        # make sure we are getting the same instance back
        self.assertTrue(desc is desc2)

        desc3 = descriptor.get_from_location(
            bundle_type,
            self.tk.pipeline_configuration,
            {"type": "app_store", "version": "v0.1.3", "name": "tk-bundle"}
        )
        # note that we don't use the equality operator here but using 'is' to
        # make sure we are getting the same instance back
        self.assertTrue(desc is not desc3)

    def _test_manual_descriptor_location(self, bundle_type, bundle_location):
        """
        Tests a manual descriptor bundle path for the given bundle type and location.

        :param bundle_type: One of descriptor.AppDescriptor.{APP,ENGINE,FRAMEWORK}
        :param bundle_location: Location in the pipeline configuration where bundles of the given
            type get installed.
        """

        desc = descriptor.get_from_location(
            bundle_type,
            self.tk.pipeline_configuration,
            {"type": "manual", "version": "v0.1.2", "name": "tk-bundle"}
        )
        self.assertEqual(
            desc.get_path(),
            os.path.join(
                bundle_location,
                "manual",
                "tk-bundle",
                "v0.1.2"
            )
        )


    def _test_dev_descriptor_location(self, bundle_type, bundle_location):
        """
        Tests a dev descriptor bundle path for the given bundle_type and bundle_location.
        Note that the bundle type and location should not have any impact on this descriptor
        type.

        :param bundle_type: One of descriptor.AppDescriptor.{APP,ENGINE,FRAMEWORK}
        :param bundle_location: Location in the pipeline configuration where bundles of the given
            type get installed.
        """
        desc = descriptor.get_from_location(
            bundle_type,
            self.tk.pipeline_configuration,
            {"type": "dev", "path": "path/to/bundle"}
        )
        self.assertEqual(desc.get_path(), os.path.join("path", "to", "bundle"))

        desc = descriptor.get_from_location(
            bundle_type,
            self.tk.pipeline_configuration,
            {"type": "dev", "path": "{PIPELINE_CONFIG}/bundle"}
        )
        self.assertEqual(
            desc.get_path(),
            os.path.join(self.tk.pipeline_configuration.get_path(), "bundle")
        )

    def _test_git_descriptor_location_with_repo(self, bundle_type, bundle_location, repo):
        """
        Tests a git descriptor bundle path for the given bundle type and location and a given
        repo.

        :param bundle_type: One of descriptor.AppDescriptor.{APP,ENGINE,FRAMEWORK}
        :param bundle_location: Location in the pipeline configuration where bundles of the given
            type get installed.
        """

        desc = descriptor.get_from_location(
            bundle_type,
            self.tk.pipeline_configuration,
            {"type": "git", "path": repo, "version": "v0.1.2"}
        )
        self.assertEqual(
            desc.get_path(),
            os.path.join(
                bundle_location,
                "git",
                os.path.basename(repo),
                "v0.1.2"
            )
        )

        # test caching
        desc2 = descriptor.get_from_location(
            bundle_type,
            self.tk.pipeline_configuration,
            {"type": "git", "path": repo, "version": "v0.1.2"}
        )
        # note that we don't use the equality operator here but using 'is' to
        # make sure we are getting the same instance back
        self.assertTrue(desc is desc2)

        desc3 = descriptor.get_from_location(
            bundle_type,
            self.tk.pipeline_configuration,
            {"type": "git", "path": repo, "version": "v0.1.3"}
        )
        # note that we don't use the equality operator here but using 'is' to
        # make sure we are getting the same instance back
        self.assertTrue(desc is not desc3)

    def _test_git_descriptor_location(self, bundle_type, bundle_location):
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
            self._test_git_descriptor_location_with_repo(
                bundle_type,
                bundle_location,
                uri
            )

    def test_descriptors_location(self):
        """
        For all descriptor types and bundle types, this test validates the
        install location of the bundles (descriptor.get_path()).
        """
        bundle_types = {
            # Do not rely on get_bundles_location() to generate the expected roots since
            # we wouldn't be testing against the expected value.
            descriptor.AppDescriptor.APP: os.path.join(self.tk.pipeline_configuration.get_install_location(), "install", "apps"),
            descriptor.AppDescriptor.ENGINE: os.path.join(self.tk.pipeline_configuration.get_install_location(), "install", "engines"),
            descriptor.AppDescriptor.FRAMEWORK: os.path.join(self.tk.pipeline_configuration.get_install_location(), "install", "frameworks")
        }
        for bundle_type, bundle_location in bundle_types.iteritems():
            self._test_app_store_descriptor_location(
                bundle_type,
                bundle_location
            )
            self._test_manual_descriptor_location(
                bundle_type,
                bundle_location
            )
            self._test_dev_descriptor_location(
                bundle_type,
                bundle_location
            )
            self._test_git_descriptor_location(
                bundle_type,
                bundle_location
            )

    def test_git_version_logic(self):
        """
        Test git descriptor version logic
        """
        desc = descriptor.get_from_location(
            descriptor.AppDescriptor.APP,
            self.tk.pipeline_configuration,
            {"type": "git", "path": "git@github.com:dummy/tk-multi-dummy.git", "version": "v1.2.3"})

        # absolute match
        self.assertEqual(desc._find_latest_tag_by_pattern(["v1.2.3"], "v1.2.3"), "v1.2.3")
        self.assertEqual(desc._find_latest_tag_by_pattern(["v1.2.3", "v1.2.2"], "v1.2.3"), "v1.2.3")

        # simple matches
        self.assertEqual(desc._find_latest_tag_by_pattern(["v1.2.3", "v1.2.2"], "v1.2.x"), "v1.2.3")
        self.assertEqual(desc._find_latest_tag_by_pattern(["v1.2.3", "v1.2.2"], "v1.2.x"), "v1.2.3")
        self.assertEqual(desc._find_latest_tag_by_pattern(["v1.2.3", "v1.2.233", "v1.3.1"], "v1.3.x"), "v1.3.1")
        self.assertEqual(desc._find_latest_tag_by_pattern(["v1.2.3", "v1.2.233", "v1.3.1", "v2.3.1"], "v1.x.x"), "v1.3.1")

        # forks
        self.assertEqual(desc._find_latest_tag_by_pattern(["v1.2.3", "v1.2.233", "v1.3.1.2.3"], "v1.3.x"), "v1.3.1.2.3")
        self.assertEqual(desc._find_latest_tag_by_pattern(["v1.2.3", "v1.2.233", "v1.3.1.2.3", "v1.4.233"], "v1.3.1.x"), "v1.3.1.2.3")

        # invalids
        self.assertRaisesRegexp(TankError,
                                "Incorrect version pattern '.*'. There should be no digit after a 'x'",
                                desc._find_latest_tag_by_pattern,
                                ["v1.2.3", "v1.2.233", "v1.3.1"],
                                "v1.x.2")

