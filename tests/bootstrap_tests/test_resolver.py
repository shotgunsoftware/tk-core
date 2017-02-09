# Copyright (c) 2016 Shotgun Software Inc.
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
from mock import patch
import sgtk
from sgtk.util import ShotgunPath

from tank_test.tank_test_base import setUpModule # noqa
from tank_test.tank_test_base import TankTestBase


class TestResolverBase(TankTestBase):
    def setUp(self, no_project=False):
        super(TestResolverBase, self).setUp()

        self.install_root = os.path.join(
            self.tk.pipeline_configuration.get_install_location(),
            "install"
        )

        # set up bundle cache mock
        path = os.path.join(self.install_root, "app_store", "tk-config-test", "v0.1.2")
        self._create_info_yaml(path)

        self.config_1 = {"type": "app_store", "version": "v0.1.2", "name": "tk-config-test"}

        self._user = self.mockgun.create("HumanUser", {"login": "john.smith"})
        self._project = self.mockgun.create("Project", {"name": "my_project"})

        # set up a resolver
        self.resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="foo.maya",
            project_id=None if no_project else self._project["id"],
            bundle_cache_fallback_paths=[self.install_root]
        )

    def _create_info_yaml(self, path):
        """
        create a mock info.yml
        """
        sgtk.util.filesystem.ensure_folder_exists(path)
        fh = open(os.path.join(path, "info.yml"), "wt")
        fh.write("foo")
        fh.close()

    def _create_pc(self, code, project=None, path=None, users=[], plugin_ids=None, descriptor=None):
        """
        Creates a pipeline configuration.

        :param code: Name of the pipeline configuration.
        :param project: Project of the pipeline configuration.
        :param path: mac_path, windows_path and linux_path will be set to this.
        :param users: List of users who should be able to use this pipeline.
        :param plugin_ids: Plugin ids for the pipeline configuration.
        :param descriptor: Descriptor for the pipeline configuration

        :returns: Dictionary with keys entity_type and entity_id.
        """

        entity = self.mockgun.create(
            "PipelineConfiguration", dict(
                code=code,
                project=project,
                users=users,
                windows_path=path,
                mac_path=path,
                linux_path=path,
                # FIXME: Official schema doesn't have the plugin_ids and descriptor fields yet,
                # we'll work with sg_plugin_ids and sg_descriptor for now.
                sg_plugin_ids=plugin_ids,
                sg_descriptor=descriptor
            )
        )
        return dict(
            entity_type=entity["type"],
            entity_id=entity["id"]
        )


class TestPluginMatching(TestResolverBase):
    """
    Testing the resolver class
    """

    def test_plugin_id_matching(self):
        """
        Tests the plugin id resolve syntax
        """
        resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="foo.maya",
            project_id=self._project["id"],
            bundle_cache_fallback_paths=[self.install_root]
        )

        # test full match
        resolver._plugin_id = "foo.maya"
        self.assertTrue(resolver._match_plugin_id("*"))

        # test no match
        resolver._plugin_id = "foo.maya"
        self.assertFalse(resolver._match_plugin_id(""))
        self.assertFalse(resolver._match_plugin_id("None"))
        self.assertFalse(resolver._match_plugin_id(" "))
        self.assertFalse(resolver._match_plugin_id(",,,,"))
        self.assertFalse(resolver._match_plugin_id("."))

        # test comma separation
        resolver._plugin_id = "foo.maya"
        self.assertFalse(resolver._match_plugin_id("foo.hou, foo.may, foo.nuk"))
        self.assertTrue(resolver._match_plugin_id("foo.hou, foo.maya, foo.nuk"))

        # test comma separation
        resolver._plugin_id = "foo"
        self.assertFalse(resolver._match_plugin_id("foo.*"))
        self.assertTrue(resolver._match_plugin_id("foo*"))

        resolver._plugin_id = "foo.maya"
        self.assertTrue(resolver._match_plugin_id("foo.*"))
        self.assertTrue(resolver._match_plugin_id("foo*"))

        resolver._plugin_id = "foo.maya"
        self.assertTrue(resolver._match_plugin_id("foo.maya"))
        self.assertFalse(resolver._match_plugin_id("foo.nuke"))

    @patch("os.path.exists", return_value=True)
    def test_single_matching_id(self, _):
        """
        Picks the sandbox with the right plugin id.
        """
        self._create_pc(
            "Dev Sandbox",
            path="path_we_want",
            users=[self._user],
            plugin_ids="foo.*"
        )

        self._create_pc(
            "Dev Sandbox",
            path="path_we_dont_want",
            users=[self._user],
            plugin_ids="not.matching.plugin.id"
        )

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login="john.smith"
        )

        self.assertEqual(config._path.current_os, 'path_we_want')

    def test_no_plugin_id_matching(self):
        """
        If no plugin id match, use the fallback.
        """

        self._create_pc(
            "Primary",
            self._project,
            plugin_ids="fo3o.*",
            descriptor="sgtk:descriptor:app_store?version=v3.1.2&name=tk-config-test"
        )

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login="john.smith"
        )

        self.assertEqual(
            config._descriptor.get_dict(),
            self.config_1
        )


class TestFallbackHandling(TestResolverBase):

    def setUp(self):
        super(TestFallbackHandling, self).setUp()

        path = os.path.join(self.install_root, "app_store", "tk-config-test", "v0.1.4")
        self._create_info_yaml(path)

        self.config_2 = {"type": "app_store", "version": "v0.1.4", "name": "tk-config-test"}

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_resolve_base_config(self, find_mock):
        """
        Tests the direct config resolve, which doesn't talk to Shotgun
        """
        config = self.resolver.resolve_configuration(self.config_1, self.tk.shotgun)
        self.assertEqual(config._descriptor.get_dict(), self.config_1)

        # make sure we didn't talk to shotgun
        self.assertEqual(find_mock.called, False)

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_resolve_latest_base_config(self, find_mock):
        """
        Tests the direct config resolve for a descriptor with no version number set
        """
        # test latest version of config by omitting version number
        config_latest = {"type": "app_store", "name": "tk-config-test"}
        config = self.resolver.resolve_configuration(config_latest, self.tk.shotgun)
        # this should find the latest version
        self.assertEqual(config._descriptor.get_dict(), self.config_2)

        # make sure we didn't talk to shotgun
        self.assertEqual(find_mock.called, False)


class TestResolverPriority(TestResolverBase):
    """
    This test ensures that the following priority is respected when multiple pipeline configurations
    are found.

    1. Pipeline configuration sandbox for a project
    2. Pipeline configuration for a project
    3. Pipeline configuration sandbox for site
    4. Pipeline configuration for site.
    """

    PROJECT_PC_PATH = "project_pc_path"

    def _create_project_pc(self):
        """
        Creates a pipeline configuration for the TestCases's project. The paths will be set
        to PROJECT_PC_PATH.
        """
        return self._create_pc("Primary", self._project, self.PROJECT_PC_PATH, [], plugin_ids="foo.*")

    PROJECT_SANDBOX_PC_PATH = "project_sandbox_pc_path"

    def _create_project_sandbox_pc(self):
        """
        Creates a pipeline configuration for the TestCases's project and it's user. The paths will be set
        to PROJECT_SANDBOX_PC_PATH.
        """
        return self._create_pc(
            "Development",
            self._project,
            self.PROJECT_SANDBOX_PC_PATH,
            [self._user],
            plugin_ids="foo.*"
        )

    SITE_PC_PATH = "site_pc_path"

    def _create_site_pc(self):
        """
        Creates a pipeline configuration with no project. The paths will be set
        to SITE_PC_PATH.
        """
        return self._create_pc("Primary", None, self.SITE_PC_PATH, [], plugin_ids="foo.*")

    SITE_SANDBOX_PC_PATH = "site_sandbox_pc_path"

    def _create_site_sandbox_pc(self):
        """
        Creates a pipeline configuration with no project for the TestCases's user. The paths will be set
        to SITE_PC_PATH.
        """
        return self._create_pc("Development", None, self.SITE_SANDBOX_PC_PATH, [self._user], plugin_ids="foo.*")

    def _test_priority(self, expected_path):
        """
        Resolves a pipeline configuration and ensures it's the expected one by comparing the
        path.

        :param str expected_path: Expected value for the current platform's path.
        """
        with patch("os.path.exists", return_value=True):
            config = self.resolver.resolve_shotgun_configuration(
                pipeline_config_identifier=None,
                fallback_config_descriptor=self.config_1,
                sg_connection=self.tk.shotgun,
                current_login="john.smith"
            )
        self.assertEqual(config._path.current_os, expected_path)

    def test_resolve_site_config(self):
        """
        Makes sure a site config takes is higher priority than the fallback.
        """
        self._create_site_pc()
        self._test_priority(self.SITE_PC_PATH)

    def test_resolve_sandboxed_site_config(self):
        """
        Makes sure a sandboxed site configuration overrides the site config.
        """
        self._create_site_sandbox_pc()
        self._create_site_pc()
        self._test_priority(self.SITE_SANDBOX_PC_PATH)

    def test_resolve_project_config(self):
        """
        Makes sure a project configuration overrides the sandboxed site config.
        """
        self._create_project_pc()
        self._create_site_sandbox_pc()
        self._create_site_pc()
        self._test_priority(self.PROJECT_PC_PATH)

    def test_resolve_sandboxed_project_config(self):
        """
        Makes sure a sandboxed project configuration sandbox overrides project configuration.
        """
        self._create_project_sandbox_pc()
        self._create_project_pc()
        self._create_site_sandbox_pc()
        self._create_site_pc()
        self._test_priority(self.PROJECT_SANDBOX_PC_PATH)

    def test_resolve_pc(self):
        """
        Ensure that if there is only one pipeline configuration it will always be resolved.
        """
        link = self._create_site_pc()
        self._test_priority(self.SITE_PC_PATH)
        self.mockgun.delete(**link)

        link = self._create_site_sandbox_pc()
        self._test_priority(self.SITE_SANDBOX_PC_PATH)
        self.mockgun.delete(**link)

        link = self._create_project_pc()
        self._test_priority(self.PROJECT_PC_PATH)
        self.mockgun.delete(**link)

        link = self._create_project_sandbox_pc()
        self._test_priority(self.PROJECT_SANDBOX_PC_PATH)


class TestPipelineLocationFieldPriority(TestResolverBase):

    @patch("os.path.exists", return_value=True)
    def test_path_override(self, _):
        """
        If pipeline config paths are defined, these take precedence over the descriptor field.
        """

        self._create_pc(
            "Primary", self._project, path="sg_path", plugin_ids="foo.*",
            descriptor="sgtk:descriptor:app_store?version=v0.1.2&name=tk-config-test"
        )

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login="john.smith"
        )

        self.assertEqual(config._path.current_os, 'sg_path')

    def test_pc_descriptor(self):
        """
        Descriptor field is used when set.
        """

        self._create_pc(
            "Primary", self._project, plugin_ids="foo.*, bar, baz",
            descriptor="sgtk:descriptor:app_store?version=v3.1.2&name=tk-config-test"
        )

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login="john.smith"
        )

        self.assertEqual(
            config._descriptor.get_dict(),
            {'name': 'tk-config-test', 'type': 'app_store', 'version': 'v3.1.2'}
        )

    def test_pipeline_without_location(self):
        """
        Ensures that pipeline configurations without any location (descriptor or *_path)
         are skipped.
        """

        # First make sure we return something when there the path is set.
        pc_id = self._create_pc(
            "Primary",
            path="sg_path",
            plugin_ids="foo.*",
        )["entity_id"]

        pcs = list(self.resolver.find_matching_pipeline_configurations(
            None,
            "john.smith",
            self.mockgun
        ))
        self.assertEqual(len(pcs), 1)
        self.assertEqual(pcs[0]["id"], pc_id)

        # Now remove every locators.
        self.mockgun.update(
            "PipelineConfiguration",
            pc_id,
            {
                "windows_path": None,
                "linux_path": None,
                "mac_path": None,
                "sg_descriptor": None
            }
        )

        # Nothing should be found.
        pcs = list(self.resolver.find_matching_pipeline_configurations(
            None,
            "john.smith",
            self.mockgun
        ))
        self.assertEqual(len(pcs), 0)


class TestResolverSiteConfig(TestResolverBase):
    """
    All Test Resoolver tests, just with the site config instead of a project config
    """

    def setUp(self):
        super(TestResolverSiteConfig, self).setUp()

        # set up a resolver
        self.resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="foo.maya",
            project_id=None,
            bundle_cache_fallback_paths=[self.install_root]
        )

    @patch("os.path.exists", return_value=True)
    def test_site_override(self, _):
        """
        When multiple primaries match, the latest one is picked.
        """

        self._create_pc(
            "Primary", path="not_the_pipeline_we_want", plugin_ids="foo.*"
        )
        self._create_pc(
            "Primary", path="the_pipeline_we_want", plugin_ids="foo.*"
        )

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login="john.smith"
        )

        self.assertEqual(config._path.current_os, "the_pipeline_we_want")

    @patch("os.path.exists", return_value=True)
    def test_resolve_installed_from_sg(self, _):
        """
        When a path is set, we have an installed configuration.
        """

        self._create_pc("Primary", path="sg_path", plugin_ids="foo.*")

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login="john.smith"
        )

        self.assertIsInstance(config, sgtk.bootstrap.resolver.InstalledConfiguration)

    def test_resolve_cached_from_sg(self):
        """
        When nothing is set, we get the cached descriptor.
        """
        self._create_pc("Primary", plugin_ids="foo.*")

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login="john.smith"
        )

        self.assertIsInstance(config, sgtk.bootstrap.resolver.CachedConfiguration)


class TestResolvedConfiguration(TankTestBase):
    """
    Ensures that resolving a descriptor returns the right Configuration object.
    """

    def setUp(self):
        super(TestResolvedConfiguration, self).setUp()

        self._tmp_bundle_cache = os.path.join(self.tank_temp, "bundle_cache")
        self._resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="tk-maya",
            bundle_cache_fallback_paths=[self._tmp_bundle_cache]
        )

    def test_resolve_installed_configuration(self):
        """
        Makes sure an installed configuration is resolved.
        """
        config = self._resolver.resolve_configuration(
            {"type": "installed", "path": self.pipeline_config_root}, self.tk.shotgun
        )
        self.assertIsInstance(
            config,
            sgtk.bootstrap.resolver.InstalledConfiguration
        )
        self.assertEqual(config.has_local_bundle_cache, True)

    def test_resolve_baked_configuration(self):
        """
        Makes sure a baked configuration is resolved.
        """
        os.makedirs(
            os.path.join(self._tmp_bundle_cache, "baked", "unit_tests", "v0.4.2")
        )

        config = self._resolver.resolve_configuration(
            {"type": "baked", "name": "unit_tests", "version": "v0.4.2"}, self.tk.shotgun
        )

        self.assertIsInstance(
            config,
            sgtk.bootstrap.resolver.BakedConfiguration
        )
        self.assertEqual(config.has_local_bundle_cache, True)

    def test_resolve_cached_configuration(self):
        """
        Makes sure a cached configuration is resolved.
        """
        os.makedirs(
            os.path.join(self._tmp_bundle_cache, "app_store", "unit_tests", "v0.4.2")
        )

        config = self._resolver.resolve_configuration(
            {"type": "app_store", "name": "unit_tests", "version": "v0.4.2"}, self.tk.shotgun
        )

        self.assertIsInstance(
            config,
            sgtk.bootstrap.resolver.CachedConfiguration
        )
        self.assertEqual(config.has_local_bundle_cache, False)


class TestResolvePerId(TestResolverBase):

    @patch("os.path.exists", return_value=True)
    def test_existing_pc_ic(self, _):
        """
        Resolve an existing pipeline configuration by id.
        """
        pc_id = self._create_pc(
            "Primary", self._project, "sg_path", plugin_ids="foo.*"
        )["entity_id"]

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=pc_id,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login="john.smith"
        )

        self.assertEqual(config._path.current_os, 'sg_path')

    @patch("os.path.exists", return_value=True)
    def test_non_existing_pc_ic(self, _):
        """
        Resolve a non-existent pipeline configuration by id should fail.
        """
        with self.assertRaisesRegexp(sgtk.bootstrap.TankBootstrapError, "Pipeline configuration with id"):
            self.resolver.resolve_shotgun_configuration(
                pipeline_config_identifier=42,
                fallback_config_descriptor=self.config_1,
                sg_connection=self.tk.shotgun,
                current_login="john.smith"
            )


class TestErrorHandling(TestResolverBase):

    def test_installed_configuration_not_on_disk(self):
        """
        Ensure that the resolver detects when an installed configuration has not been set for the
        current platform.
        """
        # Create a pipeline configuration.
        pc_id = self._create_pc(
            "Primary",
            self._project,
            "sg_path",
            plugin_ids="foo.*",
        )["entity_id"]

        # Remove the current platform's path.
        self.mockgun.update(
            "PipelineConfiguration",
            pc_id,
            {
                ShotgunPath.get_shotgun_storage_key(): None
            }
        )

        with self.assertRaisesRegexp(sgtk.bootstrap.TankBootstrapError, "The Toolkit configuration path has not"):
            self.resolver.resolve_shotgun_configuration(
                pipeline_config_identifier=pc_id,
                fallback_config_descriptor=self.config_1,
                sg_connection=self.tk.shotgun,
                current_login="john.smith"
            )
