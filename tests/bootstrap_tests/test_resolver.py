# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import itertools
import os
import sys
import sgtk
from sgtk.util import ShotgunPath

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    TankTestBase,
)
from tank.bootstrap import constants


class TestResolverBase(TankTestBase):
    """
    Base class for resolver tests
    """

    def setUp(self):
        super().setUp()

        self.install_root = os.path.join(
            self.tk.pipeline_configuration.get_install_location(), "install"
        )

        # set up bundle cache mock
        path = os.path.join(self.install_root, "app_store", "tk-config-test", "v0.1.2")
        self._create_info_yaml(path)

        self.config_1 = {
            "type": "app_store",
            "version": "v0.1.2",
            "name": "tk-config-test",
        }

        self._john_smith = self.mockgun.create(
            "HumanUser", {"login": "john.smith", "name": "John Smith"}
        )
        self._project = self.mockgun.create("Project", {"name": "my_project"})

        # set up a resolver
        self.resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="foo.maya",
            project_id=self._project["id"],
            bundle_cache_fallback_paths=[self.install_root],
        )

    def _create_info_yaml(self, path):
        """
        create a mock info.yml
        """
        sgtk.util.filesystem.ensure_folder_exists(path)
        with open(os.path.join(path, "info.yml"), "wt") as fh:
            fh.write("foo")

    def _create_pc(
        self,
        code,
        project=None,
        path=None,
        users=None,
        plugin_ids=None,
        descriptor=None,
        uploaded_config_dict=None,
    ):
        """
        Creates a pipeline configuration.

        :param code: Name of the pipeline configuration.
        :param project: Project of the pipeline configuration.
        :param path: mac_path, windows_path and linux_path will be set to this.
        :param users: List of users who should be able to use this pipeline.
        :param plugin_ids: Plugin ids for the pipeline configuration.
        :param descriptor: Descriptor for the pipeline configuration
        :param uploaded_config_dict: Full attachment dictionary to represent an uploaded config
        :returns: Dictionary with keys entity_type and entity_id.
        """

        return self.mockgun.create(
            "PipelineConfiguration",
            dict(
                code=code,
                project=project,
                users=users or [],
                windows_path=path,
                mac_path=path,
                linux_path=path,
                plugin_ids=plugin_ids,
                descriptor=descriptor,
                uploaded_config=uploaded_config_dict,
            ),
        )


class TestUserRestriction(TestResolverBase):
    """
    Testing the logic around user restrictions
    """

    def setUp(self):
        super().setUp()

        self._john_doe = self.mockgun.create(
            "HumanUser", {"login": "john.doe", "name": "John Doe"}
        )

        self._john_doe_pc = self._create_pc(
            "Doe Sandbox",
            users=[self._john_doe],
            plugin_ids="foo.*",
            path="/path/to/john/doe",
        )
        self._smith_pc = self._create_pc(
            "Smith Sandbox",
            users=[self._john_smith],
            plugin_ids="foo.*",
            path="/path/to/user",
        )

    def test_find_user_sandbox(self):
        """
        Ensures we can find the sandbox for the requested user.
        """
        # Make sure we can find the pipeline configuration for a specific user.
        configs = self.resolver.find_matching_pipeline_configurations(
            pipeline_config_name=None,
            current_login="john.smith",
            sg_connection=self.mockgun,
        )

        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]["id"], self._smith_pc["id"])

        configs = self.resolver.find_matching_pipeline_configurations(
            pipeline_config_name=None,
            current_login="john.doe",
            sg_connection=self.mockgun,
        )

        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0]["id"], self._john_doe_pc["id"])

        # Make sure requesting a user that isn't assigned will not return any pipeline.
        configs = self.resolver.find_matching_pipeline_configurations(
            pipeline_config_name=None,
            current_login="Batman",
            sg_connection=self.mockgun,
        )

        self.assertListEqual(configs, [])

    def test_find_shared_sandbox(self):
        """
        Ensures that sandboxes without user restrictions can be found.
        """
        shared_pc = self._create_pc(
            "Shared Sandbox", users=[], plugin_ids="foo.*", path="/path/to/user"
        )

        configs = self.resolver.find_matching_pipeline_configurations(
            pipeline_config_name=None,
            current_login="Batman",
            sg_connection=self.mockgun,
        )

        # Ensure what we only found the shared configuration because Batman doesn't own any sandboxes.
        self.assertEqual(len(configs), 1)
        self.assertEqual(shared_pc["id"], configs[0]["id"])

        configs = self.resolver.find_matching_pipeline_configurations(
            pipeline_config_name=None,
            current_login="john.smith",
            sg_connection=self.mockgun,
        )

        # Ensure we got back the right pipeline configurations for John Smith, who has access
        # to his sandbox and a shared pipeline configuration.
        self.assertEqual(
            sorted(c["id"] for c in configs), [self._smith_pc["id"], shared_pc["id"]]
        )


class TestPluginMatching(TestResolverBase):
    """
    Tests the matching of plugin ids
    """

    def test_plugin_id_matching(self):
        """
        Tests the plugin id resolve syntax
        """
        resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="foo.maya",
            project_id=self._project["id"],
            bundle_cache_fallback_paths=[self.install_root],
        )

        def _match_plugin_helper(plugin_ids):
            return resolver._matches_current_plugin_id({"plugin_ids": plugin_ids})

        # test full match
        resolver._plugin_id = "foo.maya"
        self.assertTrue(_match_plugin_helper("*"))

        # test no match
        resolver._plugin_id = "foo.maya"
        self.assertFalse(_match_plugin_helper(""))
        self.assertFalse(_match_plugin_helper("None"))
        self.assertFalse(_match_plugin_helper(" "))
        self.assertFalse(_match_plugin_helper(",,,,"))
        self.assertFalse(_match_plugin_helper("."))

        # test comma separation
        resolver._plugin_id = "foo.maya"
        self.assertFalse(_match_plugin_helper("foo.hou, foo.may, foo.nuk"))
        self.assertTrue(_match_plugin_helper("foo.hou, foo.maya, foo.nuk"))

        # test comma separation
        resolver._plugin_id = "foo"
        self.assertFalse(_match_plugin_helper("foo.*"))
        self.assertTrue(_match_plugin_helper("foo*"))

        resolver._plugin_id = "foo.maya"
        self.assertTrue(_match_plugin_helper("foo.*"))
        self.assertTrue(_match_plugin_helper("foo*"))

        resolver._plugin_id = "foo.maya"
        self.assertTrue(_match_plugin_helper("foo.maya"))
        self.assertFalse(_match_plugin_helper("foo.nuke"))

        # If the value is None then we always get back False.
        self.assertFalse(_match_plugin_helper(None))

        # Always False return, even when _plugin_id is None and the value is None.
        resolver._plugin_id = None
        self.assertFalse(_match_plugin_helper(None))
        self.assertFalse(_match_plugin_helper("foo.maya"))

    @mock.patch("os.path.isdir", return_value=True)
    def test_single_matching_id(self, _):
        """
        Picks the sandbox with the right plugin id.
        """
        self._create_pc(
            "Dev Sandbox",
            path="path_we_want",
            users=[self._john_smith],
            plugin_ids="foo.*",
        )

        self._create_pc(
            "Dev Sandbox",
            path="path_we_dont_want",
            users=[self._john_smith],
            plugin_ids="not.matching.plugin.id",
        )

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.mockgun,
            current_login="john.smith",
        )

        self.assertEqual(config._path.current_os, "path_we_want")

    def test_no_plugin_id_matching(self):
        """
        If no plugin id match, use the fallback.
        """

        self._create_pc(
            "Primary",
            self._project,
            plugin_ids="fo3o.*",
            descriptor="sgtk:descriptor:app_store?version=v3.1.2&name=tk-config-test",
        )

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.mockgun,
            current_login="john.smith",
        )

        self.assertEqual(config._descriptor.get_dict(), self.config_1)


class TestFallbackHandling(TestResolverBase):
    """
    Tests the logic for when to communicate with shotgun
    """

    def setUp(self):
        super().setUp()

        path = os.path.join(self.install_root, "app_store", "tk-config-test", "v0.1.4")
        self._create_info_yaml(path)

        self.config_2 = {
            "type": "app_store",
            "version": "v0.1.4",
            "name": "tk-config-test",
        }

    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_resolve_base_config(self, find_mock):
        """
        Tests the direct config resolve, which doesn't talk to Shotgun
        """

        config = self.resolver.resolve_configuration(self.config_1, self.mockgun)
        self.assertEqual(config._descriptor.get_dict(), self.config_1)

        # make sure we didn't talk to shotgun
        self.assertEqual(find_mock.called, False)

    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_resolve_latest_base_config(self, find_mock):
        """
        Tests the direct config resolve for a descriptor with no version number set
        """
        # test latest version of config by omitting version number
        config_latest = {"type": "app_store", "name": "tk-config-test"}
        config = self.resolver.resolve_configuration(config_latest, self.mockgun)
        # this should find the latest version
        self.assertEqual(config._descriptor.get_dict(), self.config_2)

        # make sure we didn't talk to shotgun
        self.assertEqual(find_mock.called, False)

class TestAutoUpdate(TestResolverBase):
    """
    A test class for the config resolved when
    the PTR desktop app is launched to startup the tk-desktop
    engine on a site or Project context.
    """
    def setUp(self):
        super().setUp()
        self.resolver._plugin_id = 'basic.desktop'

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
        return self._create_pc(
            "Primary", self._project, self.PROJECT_PC_PATH, [], plugin_ids="foo.*"
        )

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
            [self._john_smith],
            plugin_ids="foo.*",
        )

    SITE_PC_PATH = "site_pc_path"

    def _create_site_pc(self):
        """
        Creates a pipeline configuration with no project. The paths will be set
        to SITE_PC_PATH.
        """
        return self._create_pc(
            "Primary", None, self.SITE_PC_PATH, [], plugin_ids="foo.*"
        )

    SITE_SANDBOX_PC_PATH = "site_sandbox_pc_path"

    def _create_site_sandbox_pc(self):
        """
        Creates a pipeline configuration with no project for the TestCases's user. The paths will be set
        to SITE_PC_PATH.
        """
        return self._create_pc(
            "Development",
            None,
            self.SITE_SANDBOX_PC_PATH,
            [self._john_smith],
            plugin_ids="foo.*",
        )

    def _create_project_centralized_pc(self):
        """
        Creates a non-plugin-based pipeline configuration for a project. The paths will
        be set to PROJECT_PC_PATH
        """
        return self._create_pc("Primary", self._project, self.PROJECT_PC_PATH)

    def _create_project_centralized_sandbox_pc(self):
        """
        Creates a non-plugin-based pipeline configuration sandbox for a project and a user.
        The paths will be set to PROJECT_PC_PATH
        """
        return self._create_pc(
            "Development",
            self._project,
            self.PROJECT_SANDBOX_PC_PATH,
            [self._john_smith],
        )

    def _test_priority(self, expected_path):
        """
        Resolves a pipeline configuration and ensures it's the expected one by comparing the
        path.

        :param str expected_path: Expected value for the current platform's path.
        """
        with mock.patch("os.path.isdir", return_value=True):
            config = self.resolver.resolve_shotgun_configuration(
                pipeline_config_identifier=None,
                fallback_config_descriptor=self.config_1,
                sg_connection=self.mockgun,
                current_login="john.smith",
            )
        self.assertEqual(config._path.current_os, expected_path)

    def test_site_overrides_fallback(self):
        """
        Makes sure a site config takes is higher priority than the fallback.
        """
        self._create_site_pc()
        self._test_priority(self.SITE_PC_PATH)

    def test_site_sandbox_overrides_site(self):
        """
        Makes sure a sandboxed site configuration overrides the site config.
        """
        self._create_site_sandbox_pc()
        self._create_site_pc()
        self._test_priority(self.SITE_SANDBOX_PC_PATH)

    def test_project_overrides_any_site(self):
        """
        Makes sure a project configuration overrides the sandboxed site config.
        """
        self._create_project_pc()
        self._create_site_sandbox_pc()
        self._create_site_pc()
        self._test_priority(self.PROJECT_PC_PATH)

    def test_project_sandbox_overrides_everything(self):
        """
        Makes sure a sandboxed project configuration sandbox overrides project configuration.
        """
        self._create_project_sandbox_pc()
        self._create_project_pc()
        self._create_site_sandbox_pc()
        self._create_site_pc()
        self._test_priority(self.PROJECT_SANDBOX_PC_PATH)

    def test_resolve_one_config(self):
        """
        Ensure that if there is only one pipeline configuration it will always be resolved.
        """
        link = self._create_site_pc()
        self._test_priority(self.SITE_PC_PATH)
        self.mockgun.delete(link["type"], link["id"])

        link = self._create_site_sandbox_pc()
        self._test_priority(self.SITE_SANDBOX_PC_PATH)
        self.mockgun.delete(link["type"], link["id"])

        link = self._create_project_pc()
        self._test_priority(self.PROJECT_PC_PATH)
        self.mockgun.delete(link["type"], link["id"])

        link = self._create_project_sandbox_pc()
        self._test_priority(self.PROJECT_SANDBOX_PC_PATH)

    def test_project_primary_overrides_site_primary(self):
        """
        Ensure that site primary pipeline configurations are hidden by project primary pipeline
        configurations, but user sandboxes are all returned.
        """
        self._create_project_sandbox_pc()
        self._create_project_pc()
        self._create_site_sandbox_pc()
        self._create_site_pc()

        pcs = self.resolver.find_matching_pipeline_configurations(
            None, "john.smith", self.mockgun
        )

        self.assertEqual(len(pcs), 3)
        for pc in pcs:
            # Make sure that the pipeline is attached to a project or if it isn't ensure it is
            # a user sandbox.
            self.assertTrue(pc["project"] is not None or pc["code"] != "Primary")

    def test_centralized_primary_overrides_all_other_primaries(self):
        """
        Makes sure a Toolkit centralized pipeline configuration overrides other primaries.
        """
        self._create_project_sandbox_pc()
        self._create_project_pc()
        self._create_site_sandbox_pc()
        self._create_site_pc()
        self._create_project_centralized_pc()
        self._create_project_centralized_sandbox_pc()

        pcs = self.resolver.find_matching_pipeline_configurations(
            None, "john.smith", self.mockgun
        )
        # plugin-based site and project configs are hidden by the centralized primary,
        # so only the primary and the 3 sandboxes should show up.
        self.assertEqual(len(pcs), 4)

        primaries = [x for x in pcs if x["code"] == "Primary"]
        self.assertEqual(len(primaries), 1)
        self.assertEqual(primaries[0]["project"], self._project)
        self.assertEqual(primaries[0]["plugin_ids"], None)

    @mock.patch("os.path.isdir", return_value=True)
    def test_more_recent_pipeline_is_shadowed(self, _):
        """
        When two pipeline configurations could have be chosen during resolve_shotgun_configuration
        because they were of the same type, ensure we are always returning the one with the lowest id.
        """
        self._create_pc("Primary", path="first_pipeline_path", plugin_ids="foo.*")
        self._create_pc("Primary", path="second_pipeline_path", plugin_ids="foo.*")
        self._create_pc("Primary", path="third_pipeline_path", plugin_ids="foo.*")

        config = self.resolver.resolve_shotgun_configuration(
            None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.mockgun,
            current_login="john.smith",
        )

        self.assertEqual(config._path.current_os, "first_pipeline_path")

    def test_primary_ordering(self):
        """
        Ensure that the sorting algorithm for primaries is valid for any
        permutation of primaries.
        """

        primaries = [
            {"code": "Primary", "plugin_ids": "foo.bar", "id": 1},
            {"code": "Primary", "plugin_ids": "foo.bar", "id": 2},
            {"code": "Primary", "plugin_ids": None, "id": 3},
            {"code": "Primary", "plugin_ids": "foo.bar", "id": 4},
            {"code": "Primary", "plugin_ids": "foo.bar", "id": 5},
            {"code": "Primary", "plugin_ids": None, "id": 6},
        ]
        for mixed_primaries in itertools.permutations(primaries):
            self.assertEqual(
                self.resolver._pick_primary_pipeline_config(
                    mixed_primaries, "something"
                )["id"],
                3,
            )

    def test_pipeline_configuration_ordering(self):
        """
        Ensure that the sorting algorithm for pipeline configurations is valid for any
        permutation of pipeline configurations.
        """

        pcs = [
            {
                "code": "Primary",
                "project": self._project,
                "id": 1,
            },  # This one goes in front.
            {"code": "lowercase sandbox", "project": None, "id": 2},
            {"code": "lowercase sandbox", "project": None, "id": 3},
            {"code": "lowercase sandbox", "project": self._project, "id": 4},
            {"code": "lowercase sandbox", "project": self._project, "id": 5},
            {"code": "Uppercase Sandbox", "project": None, "id": 6},
            {"code": "Uppercase Sandbox", "project": None, "id": 7},
            {"code": "Uppercase Sandbox", "project": self._project, "id": 8},
            {"code": "Uppercase Sandbox", "project": self._project, "id": 9},
        ]

        for mixed_pcs in itertools.permutations(pcs):
            sorted_pcs = self.resolver._sort_pipeline_configurations(mixed_pcs)

            self.assertListEqual(pcs, sorted_pcs)


class TestPipelineLocationFieldPriority(TestResolverBase):
    """
    Tests the field priority between descriptor, xxx_path and uploaded_config
    """

    @mock.patch("os.path.isdir", return_value=True)
    def test_path_override(self, _):
        """
        If pipeline config paths are defined, these take precedence over the descriptor field.
        """

        self._create_pc(
            "Primary",
            self._project,
            path="sg_path",
            plugin_ids="foo.*",
            descriptor="sgtk:descriptor:app_store?version=v0.1.2&name=tk-config-test",
            uploaded_config_dict={
                "name": "v1.2.3.zip",
                "url": "https://...",
                "content_type": "application/zip",
                "type": "Attachment",
                "id": 139,
                "link_type": "upload",
            },
        )

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.mockgun,
            current_login="john.smith",
        )

        self.assertEqual(config._path.current_os, "sg_path")

    def test_pc_descriptor(self):
        """
        Test that descriptor field is used when set.
        """
        self._create_pc(
            "Primary",
            self._project,
            plugin_ids="foo.*, bar, baz",
            descriptor="sgtk:descriptor:app_store?version=v3.1.2&name=tk-config-test",
            uploaded_config_dict={
                "name": "v1.2.3.zip",
                "url": "https://...",
                "content_type": "application/zip",
                "type": "Attachment",
                "id": 139,
                "link_type": "upload",
            },
        )

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.mockgun,
            current_login="john.smith",
        )

        self.assertEqual(
            config._descriptor.get_dict(),
            {"name": "tk-config-test", "type": "app_store", "version": "v3.1.2"},
        )

    def test_pc_uploaded(self):
        """
        Test that uploaded zip field is used when no descriptor or path
        """
        uploaded_config_dict = {
            "name": "v1.2.3.zip",
            "url": "https://...",
            "content_type": "application/zip",
            "type": "Attachment",
            "id": 139,
            "link_type": "upload",
        }
        pc = self._create_pc(
            "Primary",
            self._project,
            plugin_ids="foo.*, bar, baz",
            uploaded_config_dict=uploaded_config_dict,
        )

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.mockgun,
            current_login="john.smith",
        )

        self.assertEqual(
            config._descriptor.get_dict(),
            {
                "entity_type": "PipelineConfiguration",
                "field": "uploaded_config",
                "id": pc["id"],
                "type": "shotgun",
                "version": uploaded_config_dict["id"],
            },
        )

    def test_pipeline_without_location(self):
        """
        Ensures that pipeline configurations without any location (descriptor or *_path)
        are skipped.
        """

        # First make sure we return something when there the path is set.
        pc_id = self._create_pc("Primary", path="sg_path", plugin_ids="foo.*")["id"]

        pcs = self.resolver.find_matching_pipeline_configurations(
            None, "john.smith", self.mockgun
        )
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
                "descriptor": None,
            },
        )

        # Nothing should be found.
        pcs = self.resolver.find_matching_pipeline_configurations(
            None, "john.smith", self.mockgun
        )
        self.assertEqual(len(pcs), 0)

    def test_pipeline_without_current_os_path(self):
        """
        Ensures that we get back a configuration that's missing a current_os path
        and that it doesn't contain a descriptor object.
        """
        # First make sure we return something when there the path is set.
        pc_id = self._create_pc("Primary", path="sg_path", plugin_ids="foo.*")["id"]

        pcs = self.resolver.find_matching_pipeline_configurations(
            None, "john.smith", self.mockgun
        )
        self.assertEqual(len(pcs), 1)
        self.assertEqual(pcs[0]["id"], pc_id)
        self.assertIsNotNone(pcs[0]["config_descriptor"])

        field_lookup = dict(
            linux="linux_path", darwin="mac_path", win32="windows_path"
        )

        base_path = "sg_path"
        base_paths = dict(
            windows_path=base_path,
            linux_path=base_path,
            mac_path=base_path,
            descriptor=None,
        )
        base_paths[field_lookup[sys.platform]] = None

        # Now remove every locators.
        self.mockgun.update("PipelineConfiguration", pc_id, base_paths)

        # We should get back one config, though it should contain a None
        # for its "config_descriptor" key, as the lack of a path for the
        # current OS will mean we couldn't create the descriptor object.
        pcs = self.resolver.find_matching_pipeline_configurations(
            None, "john.smith", self.mockgun
        )

        self.assertEqual(len(pcs), 1)
        self.assertEqual(pcs[0]["id"], pc_id)
        self.assertEqual(pcs[0]["config_descriptor"], None)

    def test_descriptor_without_plugin(self):
        """
        Ensures only plugin based pipeline configurations are reported as valid when the descriptor
        field is set.
        """

        # First make sure we've created a valid pipeline configuration.
        pc_id = self._create_pc(
            "Primary",
            project=self._project,
            descriptor="sgtk:descriptor:app_store?version=v3.1.2&name=tk-config-test",
            plugin_ids="foo.*",
        )["id"]
        pcs = self.resolver.find_matching_pipeline_configurations(
            None, "john.smith", self.mockgun
        )
        self.assertEqual(len(pcs), 1)
        self.assertEqual(pcs[0]["id"], pc_id)

        # Not clear the plugin fields and the pipeline should not be reported by
        # find_matching_pipeline_configurations.
        self.mockgun.update("PipelineConfiguration", pc_id, {"plugin_ids": None})

        pcs = self.resolver.find_matching_pipeline_configurations(
            None, "john.smith", self.mockgun
        )
        self.assertListEqual(pcs, [])


class TestResolverSiteConfig(TestResolverBase):
    """
    All Test Resolver tests, just with the site config instead of a project config
    """

    def setUp(self):
        super().setUp()

        # set up a resolver
        self.resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="foo.maya",
            project_id=None,
            bundle_cache_fallback_paths=[self.install_root],
        )

    @mock.patch("os.path.isdir", return_value=True)
    def test_resolve_installed_from_sg(self, _):
        """
        When a path is set, we have an installed configuration.
        """

        self._create_pc("Primary", path="sg_path", plugin_ids="foo.*")

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.mockgun,
            current_login="john.smith",
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
            sg_connection=self.mockgun,
            current_login="john.smith",
        )

        self.assertIsInstance(config, sgtk.bootstrap.resolver.CachedConfiguration)


class TestResolvedConfiguration(TankTestBase):
    """
    Ensures that resolving a descriptor returns the right Configuration object.
    """

    def setUp(self):
        super().setUp()

        self._tmp_bundle_cache = os.path.join(self.tank_temp, "bundle_cache")
        self._resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="tk-maya", bundle_cache_fallback_paths=[self._tmp_bundle_cache]
        )

    def test_resolve_installed_configuration(self):
        """
        Makes sure an installed configuration is resolved.
        """
        # note: this is using the centralized config that is part of the
        #       std test fixtures.
        config = self._resolver.resolve_shotgun_configuration(
            self.tk.pipeline_configuration.get_shotgun_id(),
            "sgtk:descriptor:not?a=descriptor",
            self.mockgun,
            "john.smith",
        )
        self.assertIsInstance(config, sgtk.bootstrap.resolver.InstalledConfiguration)

    def test_resolve_baked_configuration(self):
        """
        Makes sure a baked configuration is resolved.
        """
        os.makedirs(
            os.path.join(self._tmp_bundle_cache, "baked", "unit_tests", "v0.4.2")
        )

        config = self._resolver.resolve_configuration(
            {"type": "baked", "name": "unit_tests", "version": "v0.4.2"}, self.mockgun
        )

        self.assertIsInstance(config, sgtk.bootstrap.resolver.BakedConfiguration)

    def test_resolve_cached_configuration(self):
        """
        Makes sure a cached configuration is resolved.
        """
        os.makedirs(
            os.path.join(self._tmp_bundle_cache, "app_store", "unit_tests", "v0.4.2")
        )

        config = self._resolver.resolve_configuration(
            {"type": "app_store", "name": "unit_tests", "version": "v0.4.2"},
            self.mockgun,
        )

        self.assertIsInstance(config, sgtk.bootstrap.resolver.CachedConfiguration)


class TestResolvedLatestConfiguration(TankTestBase):
    """
    Ensures that resolving a descriptor with no version specified returns the right Configuration object.
    """

    def setUp(self):
        super().setUp()

        self._tmp_bundle_cache = os.path.join(self.tank_temp, "bundle_cache")
        self._resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="tk-maya", bundle_cache_fallback_paths=[self._tmp_bundle_cache]
        )

    def test_resolve_latest_cached_configuration(self):
        """
        Makes sure a cached configuration is resolved.
        """

        os.makedirs(
            os.path.join(self._tmp_bundle_cache, "app_store", "latest_test", "v0.1.0")
        )

        config = self._resolver.resolve_configuration(
            {"type": "app_store", "name": "latest_test"}, self.mockgun
        )

        self.assertEqual(
            config.descriptor.get_uri(),
            "sgtk:descriptor:app_store?name=latest_test&version=v0.1.0",
        )

        os.makedirs(
            os.path.join(self._tmp_bundle_cache, "app_store", "latest_test", "v0.1.1")
        )

        config = self._resolver.resolve_configuration(
            {"type": "app_store", "name": "latest_test"}, self.mockgun
        )

        self.assertEqual(
            config.descriptor.get_uri(),
            "sgtk:descriptor:app_store?name=latest_test&version=v0.1.1",
        )

        # make sure direct lookup also works
        config = self._resolver.resolve_configuration(
            {"type": "app_store", "name": "latest_test", "version": "v0.1.0"},
            self.mockgun,
        )

        self.assertEqual(
            config.descriptor.get_uri(),
            "sgtk:descriptor:app_store?name=latest_test&version=v0.1.0",
        )

        config = self._resolver.resolve_configuration(
            {"type": "app_store", "name": "latest_test", "version": "v0.1.1"},
            self.mockgun,
        )

        self.assertEqual(
            config.descriptor.get_uri(),
            "sgtk:descriptor:app_store?name=latest_test&version=v0.1.1",
        )


class TestResolveWithFilter(TestResolverBase):
    @mock.patch("os.path.isdir", return_value=True)
    def test_existing_pc_ic(self, _):
        """
        Resolve an existing pipeline configuration by id.
        """
        pc_id = self._create_pc(
            "Primary", self._project, "sg_path", plugin_ids="foo.*"
        )["id"]

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=pc_id,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.mockgun,
            current_login="john.smith",
        )

        self.assertEqual(config._path.current_os, "sg_path")

    @mock.patch("os.path.isdir", return_value=True)
    def test_non_existing_pc_ic(self, _):
        """
        Resolve a non-existent pipeline configuration by id should fail.
        """
        with self.assertRaisesRegex(
            sgtk.bootstrap.TankBootstrapError, "Pipeline configuration with id"
        ):
            self.resolver.resolve_shotgun_configuration(
                pipeline_config_identifier=42,
                fallback_config_descriptor=self.config_1,
                sg_connection=self.mockgun,
                current_login="john.smith",
            )

    @mock.patch("os.path.isdir", return_value=True)
    def test_resolve_by_name(self, _):
        """
        Ensure that specifying for pipeline by name works.
        """

        # Create a second user that will own similar sandboxes.
        self.mockgun.create("HumanUser", {"login": "john.doe", "name": "John Doe"})

        # Create site primary
        self._create_pc("Primary", path="primary_configuration", plugin_ids="foo.*")

        # Create a second user that will own similar sandboxes.
        john_doe = self.mockgun.create(
            "HumanUser", {"login": "john.doe", "name": "John Doe"}
        )

        for user in [john_doe, self._john_smith]:
            # Create project sandbox.
            self._create_pc(
                "Project sandbox",
                path="project_sandbox",
                plugin_ids="foo.*",
                users=[user],
                project=self._project,
            )
            # Create site sandbox.
            self._create_pc(
                "Site sandbox", path="site_sandbox", plugin_ids="foo.*", users=[user]
            )

        # Ensure we are resolving only three and they are the primary or owned by John Smith.
        pcs = self.resolver.find_matching_pipeline_configurations(
            pipeline_config_name=None,
            current_login="john.smith",
            sg_connection=self.mockgun,
        )
        self.assertEqual(len(pcs), 3)
        for pc in pcs:
            self.assertTrue(
                pc["code"] == "Primary"
                or pc["users"][0]["id"] == self._john_smith["id"]
            )

        # Ensure we are resolving only the primary sandbox.
        pcs = self.resolver.find_matching_pipeline_configurations(
            pipeline_config_name="Primary",
            current_login="john.smith",
            sg_connection=self.mockgun,
        )
        self.assertEqual(len(pcs), 1)
        self.assertEqual(pcs[0]["code"], "Primary")

        # Ensure we are resolving the project sandbox from John Doe.
        pcs = self.resolver.find_matching_pipeline_configurations(
            pipeline_config_name="Site sandbox",
            current_login="john.doe",
            sg_connection=self.mockgun,
        )

        self.assertEqual(len(pcs), 1)
        pc = pcs[0]
        self.assertEqual(pc["code"], "Site sandbox")
        self.assertEqual(pc["users"][0]["id"], john_doe["id"])

        # Ensure we are resolving the project sandbox from John Smith.
        pcs = self.resolver.find_matching_pipeline_configurations(
            pipeline_config_name="Site sandbox",
            current_login="john.smith",
            sg_connection=self.mockgun,
        )

        self.assertEqual(len(pcs), 1)
        pc = pcs[0]
        self.assertEqual(pc["code"], "Site sandbox")
        self.assertEqual(pc["users"][0]["id"], self._john_smith["id"])


class TestErrorHandling(TestResolverBase):
    def test_installed_configuration_not_on_disk(self):
        """
        Ensure that the resolver detects when an installed configuration has not been set for the
        current platform.
        """
        # Create a pipeline configuration.
        pc_id = self._create_pc(
            "Primary", self._project, "sg_path", plugin_ids="foo.*"
        )["id"]

        # Remove the current platform's path.
        self.mockgun.update(
            "PipelineConfiguration",
            pc_id,
            {ShotgunPath.get_shotgun_storage_key(): None},
        )

        with self.assertRaisesRegex(
            sgtk.bootstrap.TankBootstrapError,
            "The PTR pipeline configuration with id %s has no source location specified for "
            "your operating system." % pc_id,
        ):
            self.resolver.resolve_shotgun_configuration(
                pipeline_config_identifier=pc_id,
                fallback_config_descriptor=self.config_1,
                sg_connection=self.mockgun,
                current_login="john.smith",
            )

    def test_invalid_descriptors_without_plugin_id_cant_break_enumeration(self):
        """
        Ensure pipeline configurations that have a broken descriptor do not prevent enumeration.
        """
        self._create_pc(
            "Primary",
            # We're creating a descriptor to something we can't possibly have cached locally.
            descriptor="sgtk:descriptor:app_store?name=tk-unknown-config",
        )

        with mock.patch(
            "tank.descriptor.io_descriptor.appstore.IODescriptorAppStore.has_remote_access",
            return_value=False,
        ):
            self.resolver.find_matching_pipeline_configurations(
                pipeline_config_name=None,
                current_login="john.smith",
                sg_connection=self.mockgun,
            )

    def test_configuration_not_found_on_disk(self):
        """
        Ensure that the resolver detects when an installed configuration is not available for the
        current platform.
        """
        this_path_does_not_exists = "/this/does/not/exists/on/disk"
        pc_id = self._create_pc("Primary", None, this_path_does_not_exists)["id"]

        expected_descriptor_dict = ShotgunPath(
            this_path_does_not_exists,
            this_path_does_not_exists,
            this_path_does_not_exists,
        ).as_shotgun_dict()
        expected_descriptor_dict["type"] = "path"

        with self.assertRaisesRegex(
            sgtk.bootstrap.TankBootstrapError,
            "Installed pipeline configuration '.*' does not exist on disk!",
        ):
            self.resolver.resolve_shotgun_configuration(
                pc_id, [], self.mockgun, "john.smith"
            )
