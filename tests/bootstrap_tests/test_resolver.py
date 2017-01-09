# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
from mock import patch
import sgtk

from tank_test.tank_test_base import setUpModule, TankTestBase # noqa


class TestResolver(TankTestBase):
    """
    Testing the resolver class
    """

    def setUp(self):
        super(TestResolver, self).setUp()

        self.install_root = os.path.join(
            self.tk.pipeline_configuration.get_install_location(),
            "install"
        )

        # set up bundle cache mock
        path = os.path.join(self.install_root, "app_store", "tk-config-test", "v0.1.2")
        self._create_info_yaml(path)
        path = os.path.join(self.install_root, "app_store", "tk-config-test", "v0.1.4")
        self._create_info_yaml(path)

        self.config_1 = {"type": "app_store", "version": "v0.1.2", "name": "tk-config-test"}
        self.config_2 = {"type": "app_store", "version": "v0.1.4", "name": "tk-config-test"}

        # set up a resolver
        self.resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="foo.maya",
            engine_name="tk-test",
            project_id=123,
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

    def test_plugin_resolve(self):
        """
        Tests the plugin id resolve syntax
        """
        resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="foo.maya",
            engine_name="tk-test",
            project_id=123,
            bundle_cache_fallback_paths=[self.install_root]
        )

        # test full match
        resolver._plugin_id="foo.maya"
        self.assertTrue(resolver._match_plugin_id("*"))

        # test no match
        resolver._plugin_id="foo.maya"
        self.assertFalse(resolver._match_plugin_id(""))
        self.assertFalse(resolver._match_plugin_id("None"))
        self.assertFalse(resolver._match_plugin_id(" "))
        self.assertFalse(resolver._match_plugin_id(",,,,"))
        self.assertFalse(resolver._match_plugin_id("."))

        # test comma separation
        resolver._plugin_id="foo.maya"
        self.assertFalse(resolver._match_plugin_id("foo.hou, foo.may, foo.nuk"))
        self.assertTrue(resolver._match_plugin_id("foo.hou, foo.maya, foo.nuk"))

        # test comma separation
        resolver._plugin_id="foo"
        self.assertFalse(resolver._match_plugin_id("foo.*"))
        self.assertTrue(resolver._match_plugin_id("foo*"))

        resolver._plugin_id="foo.maya"
        self.assertTrue(resolver._match_plugin_id("foo.*"))
        self.assertTrue(resolver._match_plugin_id("foo*"))

        resolver._plugin_id="foo.maya"
        self.assertTrue(resolver._match_plugin_id("foo.maya"))
        self.assertFalse(resolver._match_plugin_id("foo.nuke"))

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

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_auto_resolve_query(self, find_mock):
        """
        Test the sg syntax for the sg auto resolve syntax, e.g. when no pc is defined
        """

        def find_mock_impl(*args, **kwargs):
            # expect the following:
            # args:
            # ('PipelineConfiguration',
            #  [{'filter_operator': 'all', 'filters': [['project', 'is', {'type': 'Project', 'id': 123}], {'filter_operator': 'any', 'filters': [['code', 'is', 'Primary'], ['users.HumanUser.login', 'contains', 'john.smith']]}]}],
            #  ['code', 'users', 'plugin_ids', 'sg_plugin_ids', 'windows_path', 'linux_path', 'mac_path', 'sg_descriptor', 'descriptor'])
            #
            #
            # kwargs:
            # {'order': [{'direction': 'asc', 'field_name': 'updated_at'}]}
            if args[0] == "PipelineConfiguration":
                self.assertEqual(
                    args[1],
                    [{'filter_operator': 'all', 'filters': [{'filter_operator': 'any', 'filters': [['project', 'is', {'type': 'Project', 'id': 123}], ['project', 'is', None]]}, {'filter_operator': 'any', 'filters': [['code', 'is', 'Primary'], ['users.HumanUser.login', 'contains', 'john.smith']]}]}]
                )

                self.assertEqual(
                    args[2],
                    ['code', 'project', 'users', 'plugin_ids', 'sg_plugin_ids', 'windows_path', 'linux_path', 'mac_path', 'sg_descriptor', 'descriptor']
                )

            return []

        find_mock.side_effect = find_mock_impl

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_name=None,
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

            # expect the following:
            # args:
            # (
            # 'PipelineConfiguration',
            # [['project', 'is', {'type': 'Project', 'id': 123}], ['code', 'is', 'dev_sandbox']],
            # ['code', 'users', 'plugin_ids', 'sg_plugin_ids', 'windows_path', 'linux_path', 'mac_path', 'sg_descriptor', 'descriptor']
            # )
            #
            # kwargs:
            # {'order': [{'direction': 'asc', 'field_name': 'updated_at'}]}
            if args[0] == "PipelineConfiguration":
                self.assertEqual(
                    args[1],
                    [['project', 'is', {'type': 'Project', 'id': 123}], ['code', 'is', 'dev_sandbox']]
                )

                self.assertEqual(
                    args[2],
                    ['code', 'project', 'users', 'plugin_ids', 'sg_plugin_ids', 'windows_path', 'linux_path', 'mac_path', 'sg_descriptor', 'descriptor']
                )

            return []

        find_mock.side_effect = find_mock_impl

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_name="dev_sandbox",
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertEqual(config._descriptor.get_dict(), self.config_1)

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    @patch("os.path.exists", return_value=True)
    def test_auto_resolve_primary(self, _, find_mock):
        """
        Resolve the primrary config when no configuration name is specified.
        """

        def find_mock_impl(*args, **kwargs):
            return [{
                'code': 'Primary',
                'project': {'type': 'Project', 'id': 123},
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
            pipeline_config_name=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertEqual(config.path, 'sg_path')

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    @patch("os.path.exists", return_value=True)
    def test_auto_resolve_user(self, _, find_mock):
        """
        When a user config is specified, this takes precedence over primary
        """

        def find_mock_impl(*args, **kwargs):
            return [{
                'code': 'Primary',
                'users': [],
                'project': {'type': 'Project', 'id': 123},
                'plugin_ids': "foo.*",
                'sg_plugin_ids': None,
                'windows_path': 'pr_path',
                'linux_path': 'pr_path',
                'mac_path': 'pr_path',
                'sg_descriptor': None,
                'descriptor': None
            },
            {
                'code': 'Dev Sandbox',
                'users': [],
                'project': {'type': 'Project', 'id': 123},
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
            pipeline_config_name=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertEqual(config.path, 'sg_path')

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    @patch("os.path.exists", return_value=True)
    def test_site_override(self, _, find_mock):
        """
        if both a site and a project config matches, the project config takes precedence
        """

        def find_mock_impl(*args, **kwargs):
            return [{
                'code': 'Primary',
                'users': [],
                'project': {'type': 'Project', 'id': 123},
                'plugin_ids': "foo.*",
                'sg_plugin_ids': None,
                'windows_path': 'pr_path',
                'linux_path': 'pr_path',
                'mac_path': 'pr_path',
                'sg_descriptor': None,
                'descriptor': None
            },
            {
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
            pipeline_config_name=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertEqual(config.path, 'pr_path')

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    @patch("os.path.exists", return_value=True)
    def test_site_override_2(self, _, find_mock):
        """
        Picks the sandbox with the right plugin id.
        """

        def find_mock_impl(*args, **kwargs):
            return [
            {
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
            },

            {
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
            pipeline_config_name=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertEqual(config.path, 'sg_path')

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    @patch("os.path.exists", return_value=True)
    def test_specific_resolve(self, _, find_mock):
        """
        Resolve the sandbox if no primary is present.
        """

        def find_mock_impl(*args, **kwargs):
            return [{
                'code': 'Dev Sandbox',
                'project': {'type': 'Project', 'id': 123},
                'users': [],
                'plugin_ids': "foo.maya",
                'sg_plugin_ids': None,
                'windows_path': 'sg_path',
                'linux_path': 'sg_path',
                'mac_path': 'sg_path',
                'sg_descriptor': None,
                'descriptor': None
                }]

        find_mock.side_effect = find_mock_impl

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_name="Dev Sandbox",
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertEqual(config.path, 'sg_path')

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    @patch("os.path.exists", return_value=True)
    def test_path_override(self, _, find_mock):
        """
        If pipeline config paths are defined, these take precedence over the descriptor field.
        """

        def find_mock_impl(*args, **kwargs):
            return [{
                'code': 'Primary',
                'project': {'type': 'Project', 'id': 123},
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
            pipeline_config_name="Dev Sandbox",
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertEqual(config.path, 'sg_path')

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_pc_descriptor(self, find_mock):
        """
        Descriptor field is used when set.
        """

        def find_mock_impl(*args, **kwargs):
            return [{
                'code': 'Primary',
                'project': {'type': 'Project', 'id': 123},
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
            pipeline_config_name="Dev Sandbox",
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertEqual(
            config._descriptor.get_dict(),
            {'name': 'tk-config-test', 'type': 'app_store', 'version': 'v3.1.2'}
        )

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_plugin_ids(self, find_mock):
        """
        If no plugin id match, use the fallback.
        """

        def find_mock_impl(*args, **kwargs):
            return [{
                'code': 'Primary',
                'project': {'type': 'Project', 'id': 123},
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
            pipeline_config_name="Dev Sandbox",
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertEqual(
            config._descriptor.get_dict(),
            self.config_1
        )


class TestResolverSiteConfig(TestResolver):
    """
    All Test Resoolver tests, just with the site config instead of a project config
    """

    def setUp(self):
        super(TestResolverSiteConfig, self).setUp()

        # set up a resolver
        self.resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="foo.maya",
            engine_name="tk-test",
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
                    [{'filter_operator': 'all', 'filters': [{'filter_operator': 'any', 'filters': [['project', 'is', None], ['project', 'is', None]]}, {'filter_operator': 'any', 'filters': [['code', 'is', 'Primary'], ['users.HumanUser.login', 'contains', 'john.smith']]}]}]
                )

                self.assertEqual(
                    args[2],
                    ['code', 'project', 'users', 'plugin_ids', 'sg_plugin_ids', 'windows_path', 'linux_path', 'mac_path', 'sg_descriptor', 'descriptor']
                )

            return []

        find_mock.side_effect = find_mock_impl

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_name=None,
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
                    [['project', 'is', None], ['code', 'is', 'dev_sandbox']]
                )

                self.assertEqual(
                    args[2],
                    ['code', 'project', 'users', 'plugin_ids', 'sg_plugin_ids', 'windows_path', 'linux_path', 'mac_path', 'sg_descriptor', 'descriptor']
                )

            return []

        find_mock.side_effect = find_mock_impl

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_name="dev_sandbox",
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
            },
            {
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
            pipeline_config_name=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login='john.smith'
        )

        self.assertEqual(config.path, 'sg_path')
