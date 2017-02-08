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

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    @patch("os.path.exists", return_value=True)
    def test_single_matching_id(self, _, find_mock):
        """
        Picks the sandbox with the right plugin id.
        """

        def find_mock_impl(*args, **kwargs):
            return [{
                'code': 'Dev Sandbox',
                'users': [],
                'project': None,
                'plugin_ids': "foo.*",
                'sg_plugin_ids': None,
                'windows_path': 'sg_path',
                'linux_path': 'sg_path',
                'mac_path': 'sg_path',
                'sg_descriptor': None,
                'descriptor': None
            }, {
                'code': 'Dev Sandbox',
                'users': [],
                'project': None,
                'plugin_ids': "not matching plugin ids",
                'sg_plugin_ids': None,
                'windows_path': 'nm_path',
                'linux_path': 'nm_path',
                'mac_path': 'nm_path',
                'sg_descriptor': None,
                'descriptor': None
            }
            ]

        find_mock.side_effect = find_mock_impl

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertEqual(config._path.current_os, 'sg_path')

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_no_plugin_id_matching(self, find_mock):
        """
        If no plugin id match, use the fallback.
        """

        def find_mock_impl(*args, **kwargs):
            return [{
                'code': 'Primary',
                'project': self._project,
                'users': [],
                'plugin_ids': "fo3o.*",
                'sg_plugin_ids': None,
                'windows_path': None,
                'linux_path': None,
                'mac_path': None,
                'sg_descriptor': None,
                'descriptor': 'sgtk:descriptor:app_store?version=v3.1.2&name=tk-config-test'
            }]

        find_mock.side_effect = find_mock_impl

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
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
        self.assertFalse(find_mock.called)

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
        self.assertFalse(find_mock.called)


class TestResolverProjectQuery(TestResolverBase):

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_auto_resolve_query(self, find_mock):
        """
        Test the sg syntax for the sg auto resolve syntax, e.g. when no pc is defined
        """

        def find_mock_impl(*args, **kwargs):
            if args[0] == "PipelineConfiguration":
                self.assertEqual(
                    args[1],
                    [
                        {
                            'filter_operator': 'all',
                            'filters': [
                                {
                                    'filter_operator': 'any',
                                    'filters': [
                                        ['project', 'is', {'type': 'Project', 'id': 123}],
                                        ['project', 'is', None]
                                    ]
                                },
                                {
                                    'filter_operator': 'any',
                                    'filters': [
                                        ['code', 'is', 'Primary'],
                                        ['users.HumanUser.login', 'contains', 'john.smith']
                                    ]
                                }]
                        }
                    ]
                )

                self.assertEqual(
                    args[2],
                    ['code', 'project', 'users', 'plugin_ids', 'sg_plugin_ids',
                     'windows_path', 'linux_path', 'mac_path', 'sg_descriptor', 'descriptor']
                )

                self.assertEqual(kwargs["order"], [{'direction': 'asc', 'field_name': 'updated_at'}])

            return []

        find_mock.side_effect = find_mock_impl

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertEqual(config._descriptor.get_dict(), self.config_1)

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_specific_resolve_query(self, find_mock):
        """
        Test the sg syntax for the sg auto resolve syntax, e.g. when no pc is defined
        """

        def find_mock_impl(*args, **kwargs):
            if args[0] == "PipelineConfiguration":
                self.assertEqual(
                    args[1],
                    [
                        {
                            'filter_operator': 'all',
                            'filters': [
                                {
                                    'filter_operator': 'any',
                                    'filters': [
                                        ['project', 'is', {'type': 'Project', 'id': 123}],
                                        ['project', 'is', None]
                                    ]
                                },
                                {
                                    'filter_operator': 'any',
                                    'filters': [
                                        ['code', 'is', 'dev_sandbox'],
                                        ['users.HumanUser.login', 'contains', 'john.smith']
                                    ]
                                }]
                        }
                    ]
                )

                self.assertEqual(
                    args[2],
                    ['code', 'project', 'users', 'plugin_ids', 'sg_plugin_ids',
                     'windows_path', 'linux_path', 'mac_path', 'sg_descriptor', 'descriptor']
                )

                self.assertEqual(kwargs["order"], [{'direction': 'asc', 'field_name': 'updated_at'}])

            return []

        find_mock.side_effect = find_mock_impl

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier="dev_sandbox",
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertEqual(config._descriptor.get_dict(), self.config_1)


class TestResolverSiteQuery(TestResolverBase):

    def setUp(self):
        super(TestResolverSiteQuery, self).setUp(no_project=True)

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_specific_resolve_query(self, find_mock):
        """
        Test the sg syntax for the sg auto resolve syntax, e.g. when no pc is defined
        """
        def find_mock_impl(*args, **kwargs):

            if args[0] == "PipelineConfiguration":
                self.assertEqual(
                    args[1],
                    [
                        {
                            'filter_operator': 'all',
                            'filters': [
                                {
                                    'filter_operator': 'any',
                                    'filters': [
                                        ['project', 'is', None],
                                        ['project', 'is', None]
                                    ]
                                },
                                {
                                    'filter_operator': 'any',
                                    'filters': [
                                        ['code', 'is', 'dev_sandbox'],
                                        ['users.HumanUser.login', 'contains', 'john.smith']
                                    ]
                                }]
                        }
                    ]
                )

                self.assertEqual(
                    args[2],
                    ['code', 'project', 'users', 'plugin_ids', 'sg_plugin_ids',
                     'windows_path', 'linux_path', 'mac_path', 'sg_descriptor', 'descriptor']
                )

            return []

        find_mock.side_effect = find_mock_impl

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier="dev_sandbox",
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertEqual(config._descriptor.get_dict(), self.config_1)


class TestResolverPriority(TestResolverBase):
    """
    This test ensures that the following priority is respected when multiple pipeline configurations
    are found.

    1. Pipeline configuration sandbox for a project
    2. Pipeline configuration for a project
    3. Pipeline configuration sandbox for site
    4. Pipeline configuration for site.
    """

    # FIXME: Official schema doesn't have the plugin_ids and descriptor fields yet, we'll work
    # with sg_plugin_ids and sg_descriptor for now.

    def _create_pc(self, code, project, path, users):

        entity = self.mockgun.create(
            "PipelineConfiguration", dict(
                code=code,
                project=project,
                users=users,
                sg_plugin_ids="foo.*",
                windows_path=path,
                mac_path=path,
                linux_path=path,
                sg_descriptor=None
            )
        )
        return dict(
            entity_type=entity["type"],
            entity_id=entity["id"]
        )

    PROJECT_PC_PATH = "project_pc_path"

    def _create_project_pc(self):
        return self._create_pc("Primary", self._project, self.PROJECT_PC_PATH, [])

    # PROJECT_PC = {
    #     'code': 'Primary',
    #     'project': {'type': 'Project', 'id': 123},
    #     'users': [],
    #     # 'plugin_ids': "",
    #     'sg_plugin_ids': "foo.*",
    #     'windows_path': PROJECT_PC_PATH,
    #     'linux_path': PROJECT_PC_PATH,
    #     'mac_path': PROJECT_PC_PATH,
    #     'sg_descriptor': None,
    #     # 'descriptor': None
    # }

    PROJECT_SANDBOX_PC_PATH = "project_sandbox_pc_path"

    def _create_project_sandbox_pc(self):
        return self._create_pc(
            "Development",
            self._project,
            self.PROJECT_SANDBOX_PC_PATH,
            [self._user]
        )
    #     'code': 'Development',
    #     'project': {'type': 'Project', 'id': 123},
    #     'users': [],
    #     # 'plugin_ids': None,
    #     'sg_plugin_ids': "foo.*",
    #     'windows_path': PROJECT_SANDBOX_PC_PATH,
    #     'linux_path': PROJECT_SANDBOX_PC_PATH,
    #     'mac_path': PROJECT_SANDBOX_PC_PATH,
    #     'sg_descriptor': None,
    #     # 'descriptor': None
    # }

    SITE_PC_PATH = "site_pc_path"

    def _create_site_pc(self):
        return self._create_pc("Primary", None, self.SITE_PC_PATH, [])
    # SITE_PC = {
    #     'code': 'Primary',
    #     'project': None,
    #     'users': [],
    #     # 'plugin_ids': None,
    #     'sg_plugin_ids': "foo.*",
    #     'windows_path': SITE_PC_PATH,
    #     'linux_path': SITE_PC_PATH,
    #     'mac_path': SITE_PC_PATH,
    #     'sg_descriptor': None,
    #     # 'descriptor': None
    # }

    SITE_SANDBOX_PC_PATH = "site_sandbox_pc_path"

    def _create_site_sandbox_pc(self):
        return self._create_pc("Development", None, self.SITE_SANDBOX_PC_PATH, [self._user])
    # SITE_SANDBOX_PC = {
    #     'code': 'Development',
    #     'project': None,
    #     'users': [],
    #     # 'plugin_ids': None,
    #     'sg_plugin_ids': "foo.*",
    #     'windows_path': SITE_SANDBOX_PC_PATH,
    #     'linux_path': SITE_SANDBOX_PC_PATH,
    #     'mac_path': SITE_SANDBOX_PC_PATH,
    #     'sg_descriptor': None,
    #     # 'descriptor': None
    # }

    def _test_priority(self, expected_path):
        with patch("os.path.exists", return_value=True):
            config = self.resolver.resolve_shotgun_configuration(
                pipeline_config_identifier=None,
                fallback_config_descriptor=self.config_1,
                sg_connection=self.tk.shotgun,
                current_login='john.smith'
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

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    @patch("os.path.exists", return_value=True)
    def test_path_override(self, _, find_mock):
        """
        If pipeline config paths are defined, these take precedence over the descriptor field.
        """

        def find_mock_impl(*args, **kwargs):
            return [{
                'code': 'Primary',
                'project': self._project,
                'users': [],
                'plugin_ids': "foo.*",
                'sg_plugin_ids': None,
                'windows_path': 'sg_path',
                'linux_path': 'sg_path',
                'mac_path': 'sg_path',
                'sg_descriptor': None,
                'descriptor': 'sgtk:descriptor:app_store?version=v0.1.2&name=tk-config-test'
            }]

        find_mock.side_effect = find_mock_impl

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertEqual(config._path.current_os, 'sg_path')

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_pc_descriptor(self, find_mock):
        """
        Descriptor field is used when set.
        """

        def find_mock_impl(*args, **kwargs):
            return [{
                'code': 'Primary',
                'project': self._project,
                'users': [],
                'plugin_ids': "foo.*, bar, baz",
                'sg_plugin_ids': None,
                'windows_path': None,
                'linux_path': None,
                'mac_path': None,
                'sg_descriptor': None,
                'descriptor': 'sgtk:descriptor:app_store?version=v3.1.2&name=tk-config-test'
            }]

        find_mock.side_effect = find_mock_impl

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertEqual(
            config._descriptor.get_dict(),
            {'name': 'tk-config-test', 'type': 'app_store', 'version': 'v3.1.2'}
        )


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

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_auto_resolve_query(self, find_mock):
        """
        Test the sg syntax for the sg auto resolve syntax, e.g. when no pc is defined
        """

        def find_mock_impl(*args, **kwargs):

            if args[0] == "PipelineConfiguration":
                self.assertEqual(
                    args[1],
                    [{
                        'filter_operator': 'all',
                        'filters': [
                            {
                                'filter_operator': 'any',
                                'filters': [
                                    ['project', 'is', None], ['project', 'is', None]
                                ]
                            },
                            {
                                'filter_operator': 'any',
                                'filters': [
                                    ['code', 'is', 'Primary'], ['users.HumanUser.login', 'contains', 'john.smith']
                                ]
                            }
                        ]
                    }]
                )

                self.assertEqual(
                    args[2],
                    ['code', 'project', 'users', 'plugin_ids', 'sg_plugin_ids',
                     'windows_path', 'linux_path', 'mac_path', 'sg_descriptor', 'descriptor']
                )

            return []

        find_mock.side_effect = find_mock_impl

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertEqual(config._descriptor.get_dict(), self.config_1)

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    @patch("os.path.exists", return_value=True)
    def test_site_override(self, _, find_mock):
        """
        When multiple primaries match, the latest one is picked.
        """

        def find_mock_impl(*args, **kwargs):
            return [{
                'code': 'Primary',
                'users': [],
                'project': None,
                'plugin_ids': "foo.*",
                'sg_plugin_ids': None,
                'windows_path': 'pr_path',
                'linux_path': 'pr_path',
                'mac_path': 'pr_path',
                'sg_descriptor': None,
                'descriptor': None
            }, {
                'code': 'Primary',
                'users': [],
                'project': None,
                'plugin_ids': "foo.*",
                'sg_plugin_ids': None,
                'windows_path': 'sg_path',
                'linux_path': 'sg_path',
                'mac_path': 'sg_path',
                'sg_descriptor': None,
                'descriptor': None
            }]

        find_mock.side_effect = find_mock_impl

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertEqual(config._path.current_os, 'sg_path')

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    @patch("os.path.exists", return_value=True)
    def test_resolve_installed_from_sg(self, _, find_mock):
        """
        When a path is set, we have an installed configuration.
        """
        def find_mock_impl(*args, **kwargs):
            return [{
                'code': 'Primary',
                'users': [],
                'project': None,
                'plugin_ids': "foo.*",
                'sg_plugin_ids': None,
                'windows_path': 'sg_path',
                'linux_path': 'sg_path',
                'mac_path': 'sg_path',
                'sg_descriptor': None,
                'descriptor': None
            }]

        find_mock.side_effect = find_mock_impl

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertIsInstance(config, sgtk.bootstrap.resolver.InstalledConfiguration)

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_resolve_cached_from_sg(self, find_mock):
        """
        When nothing is set, we get the cached descriptor.
        """
        def find_mock_impl(*args, **kwargs):
            return [{
                'code': 'Primary',
                'users': [],
                'project': None,
                'plugin_ids': "foo.*",
                'sg_plugin_ids': None,
                'windows_path': None,
                'linux_path': None,
                'mac_path': None,
                'sg_descriptor': None,
                'descriptor': None
            }]

        find_mock.side_effect = find_mock_impl

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertIsInstance(config, sgtk.bootstrap.resolver.CachedConfiguration)


class TestResolvedConfiguration(TankTestBase):

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
        self.assertIsInstance(
            self._resolver.resolve_configuration(
                {"type": "installed", "path": self.pipeline_config_root}, self.tk.shotgun
            ),
            sgtk.bootstrap.resolver.InstalledConfiguration
        )

    def test_resolve_baked_configuration(self):
        """
        Makes sure a baked configuration is resolved.
        """

        os.makedirs(
            os.path.join(self._tmp_bundle_cache, "baked", "unit_tests", "v0.4.2")
        )

        self.assertIsInstance(
            self._resolver.resolve_configuration(
                {"type": "baked", "name": "unit_tests", "version": "v0.4.2"}, self.tk.shotgun
            ),
            sgtk.bootstrap.resolver.BakedConfiguration
        )

    def test_resolve_cached_configuration(self):
        """
        Makes sure a cached configuration is resolved.
        """
        os.makedirs(
            os.path.join(self._tmp_bundle_cache, "app_store", "unit_tests", "v0.4.2")
        )

        self.assertIsInstance(
            self._resolver.resolve_configuration(
                {"type": "app_store", "name": "unit_tests", "version": "v0.4.2"}, self.tk.shotgun
            ),
            sgtk.bootstrap.resolver.CachedConfiguration
        )


class TestResolvePerId(TestResolverBase):

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    @patch("os.path.exists", return_value=True)
    def test_existing_pc_ic(self, _, find_mock):
        """
        Resolve an existing pipeline configuration by id.
        """

        def find_mock_impl(*args, **kwargs):
            return [{
                'id': 1,
                'code': 'Primary',
                'project': self._project,
                'users': [],
                'plugin_ids': "foo.*",
                'sg_plugin_ids': None,
                'windows_path': 'sg_path',
                'linux_path': 'sg_path',
                'mac_path': 'sg_path',
                'sg_descriptor': None,
                'descriptor': None
            }]

        find_mock.side_effect = find_mock_impl

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=1,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertEqual(config._path.current_os, 'sg_path')

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    @patch("os.path.exists", return_value=True)
    def test_non_existing_pc_ic(self, _, find_mock):
        """
        Resolve a non-existent pipeline configuration by id should fail.
        """

        def find_mock_impl(*args, **kwargs):
            return []

        find_mock.side_effect = find_mock_impl

        with self.assertRaisesRegexp(sgtk.bootstrap.TankBootstrapError, "Pipeline configuration with id"):
            self.resolver.resolve_shotgun_configuration(
                pipeline_config_identifier=1,
                fallback_config_descriptor=self.config_1,
                sg_connection=self.tk.shotgun,
                current_login='john.smith'
            )


class TestErrorHandling(TestResolverBase):

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_installed_configuration_not_on_disk(self, find_mock):
        """
        Ensure that the resolver detects when an installed configuration has not been set for the
        current platform.
        """
        def find_mock_impl(*args, **kwargs):
            pc = {
                'id': 1,
                'code': 'Primary',
                'project': self._project,
                'users': [],
                'plugin_ids': "foo.*",
                'sg_plugin_ids': None,
                'windows_path': 'sg_path',
                'linux_path': 'sg_path',
                'mac_path': 'sg_path',
                'sg_descriptor': None,
                'descriptor': None
            }
            # Wipe the current platform's path.
            pc[ShotgunPath.get_shotgun_storage_key()] = None
            return [pc]

        find_mock.side_effect = find_mock_impl

        with self.assertRaisesRegexp(sgtk.bootstrap.TankBootstrapError, "The Toolkit configuration path has not"):
            self.resolver.resolve_shotgun_configuration(
                pipeline_config_identifier=1,
                fallback_config_descriptor=self.config_1,
                sg_connection=self.tk.shotgun,
                current_login='john.smith'
            )
