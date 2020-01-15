# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Unit tests tank updates.
"""

from __future__ import with_statement

import os
import logging

from tank_test.tank_test_base import TankTestBase, setUpModule  # noqa

from tank.platform.environment import InstalledEnvironment

from tank_test.mock_appstore import TankMockStoreDescriptor, patch_app_store


class TestSimpleUpdates(TankTestBase):
    """
    Makes sure environment code works with the app store mocker.
    """

    def setUp(self):
        """
        Prepare unit test.
        """
        TankTestBase.setUp(self)

        patcher = patch_app_store()
        self._mock_store = patcher.start()
        self.addCleanup(patcher.stop)

        # Test is running updates on the configuration files, so we'll copy the config into the
        # pipeline configuration.
        self.setup_fixtures("app_store_tests", parameters={"installed_config": True})

        self._mock_store.add_engine("tk-test", "v1.0.0")
        self._mock_store.add_application("tk-multi-nodep", "v1.0.0")
        self._mock_store.add_application("tk-multi-nodep", "v2.0.0")
        self._mock_store.add_framework("tk-framework-test", "v1.0.0")
        self._mock_store.add_framework("tk-framework-test", "v1.0.1")
        self._mock_store.add_framework("tk-framework-test", "v1.1.0")

    def test_environment(self):
        """
        Make sure we can instantiate an environment and get information about the installed apps and their descriptors.
        """
        env = InstalledEnvironment(
            os.path.join(self.project_config, "env", "simple.yml"),
            self.pipeline_configuration,
        )

        self.assertListEqual(env.get_engines(), ["tk-test"])
        self.assertListEqual(env.get_apps("tk-test"), ["tk-multi-nodep"])
        self.assertListEqual(
            env.get_frameworks(),
            [
                "tk-framework-test_v1.0.0",
                "tk-framework-test_v1.0.x",
                "tk-framework-test_v1.x.x",
            ],
        )

        desc = env.get_framework_descriptor("tk-framework-test_v1.0.0")
        self.assertIsInstance(desc._io_descriptor, TankMockStoreDescriptor)
        self.assertEqual(desc.version, "v1.0.0")

        desc = env.get_engine_descriptor("tk-test")
        self.assertIsInstance(desc._io_descriptor, TankMockStoreDescriptor)
        self.assertEqual(desc.version, "v1.0.0")

        desc = env.get_app_descriptor("tk-test", "tk-multi-nodep")
        self.assertIsInstance(desc._io_descriptor, TankMockStoreDescriptor)
        self.assertEqual(desc.version, "v1.0.0")

    def test_simple_update(self):
        """
        Test Simple update.
        """
        # Run appstore updates.
        command = self.tk.get_command("updates")
        command.set_logger(logging.getLogger("/dev/null"))
        command.execute({"environment_filter": "simple"})

        # Make sure we are v2.
        env = InstalledEnvironment(
            os.path.join(self.project_config, "env", "simple.yml"),
            self.pipeline_configuration,
        )

        desc = env.get_app_descriptor("tk-test", "tk-multi-nodep")
        self.assertEqual(desc.version, "v2.0.0")

        desc = env.get_framework_descriptor("tk-framework-test_v1.0.0")
        self.assertEqual(desc.version, "v1.0.0")

        desc = env.get_framework_descriptor("tk-framework-test_v1.0.x")
        self.assertEqual(desc.version, "v1.0.1")

        desc = env.get_framework_descriptor("tk-framework-test_v1.x.x")
        self.assertEqual(desc.version, "v1.1.0")


class TestIncludeUpdates(TankTestBase):
    """
    Tests updates to bundle within includes.
    """

    def setUp(self):
        """
        Prepares unit test with basic bundles.
        """
        TankTestBase.setUp(self)
        # Test is running updates on the configuration files, so we'll copy the config into the
        # pipeline configuration.
        self.setup_fixtures("app_store_tests", parameters={"installed_config": True})

        patcher = patch_app_store()
        self._mock_store = patcher.start()
        self.addCleanup(patcher.stop)

        self._engine_bundle = self._mock_store.add_engine("tk-engine", "v1.0.0")
        self._app_bundle = self._mock_store.add_application("tk-multi-app", "v1.0.0")
        self._2nd_level_dep_bundle = self._mock_store.add_framework(
            "tk-framework-2nd-level-dep", "v1.0.0"
        )

        self._update_cmd = self.tk.get_command("updates")
        self._update_cmd.set_logger(logging.getLogger("/dev/null"))

    def _get_env(self, env_name):
        """
        Retrieves the environment file specified.
        """
        return InstalledEnvironment(
            os.path.join(self.project_config, "env", "%s.yml" % env_name),
            self.pipeline_configuration,
        )

    def _update_env(self, env_name):
        """
        Updates given environment.

        :param name: Name of the environment to update.
        """
        self._update_cmd.execute({"environment_filter": env_name})

    def test_update_include(self):
        """
        App should be updated in the common_apps file.
        """
        # Create a new version of the app that is included and update.
        self._mock_store.add_application("tk-multi-app", "v2.0.0")
        self._update_env("updating_included_app")

        # Reload env
        env = self._get_env("updating_included_app")

        # The new version of the app should reside inside common_apps.yml
        _, file_path = env.find_location_for_app("tk-engine", "tk-multi-app")
        self.assertEqual(os.path.basename(file_path), "common_apps.yml")

        self.assertDictEqual(
            env.get_app_descriptor("tk-engine", "tk-multi-app").get_location(),
            {"name": "tk-multi-app", "version": "v2.0.0", "type": "app_store"},
        )

    def test_update_include_with_new_framework(self):
        """
        App's new dependency should be installed inside common_apps.yml.

        tk-multi-app v1.0.0 doesn't have any dependency. v2.0.0 however has a dependency
        on a new framework, tk-framework-test. This new framework has a dependency on
        tk-framework-2nd-level-dep. This second framework is however already
        installed in the updating_included_app environment. We need to make sure that
        this framework is added inside the common_apps.yml file, where the app
        is defined, because other environments might not already have the second framework
        in them. In other words, new frameworks that are installed need to be added as close
        as possible as the bundles that depend on them. This is what this test ensures.
        """
        # The 2nd level dependency is initialially available from the main environment file.
        env = self._get_env("updating_included_app")
        _, file_path = env.find_location_for_framework(
            "tk-framework-2nd-level-dep_v1.x.x"
        )
        self.assertEqual(os.path.basename(file_path), "updating_included_app.yml")

        # Create a new framework that we've never seen before.
        fwk = self._mock_store.add_framework("tk-framework-test", "v1.0.0")
        # Add a new version of the app and add give it a dependency on the new framework.
        self._mock_store.add_application(
            "tk-multi-app", "v2.0.0"
        ).required_frameworks = [fwk.get_major_dependency_descriptor()]
        self._update_env("updating_included_app")

        # Reload env
        env = self._get_env("updating_included_app")

        # The new version of the app should reside inside common_apps.yml
        _, file_path = env.find_location_for_framework("tk-framework-test_v1.x.x")
        self.assertEqual(os.path.basename(file_path), "common_apps.yml")
        desc = env.get_framework_descriptor("tk-framework-test_v1.x.x")
        self.assertEqual(desc.get_location()["version"], "v1.0.0")

        # Add another version, which this time will bring in a new framework
        # that is already being used in the environment file.
        fwk = self._mock_store.add_framework("tk-framework-test", "v1.0.1")
        fwk.required_frameworks = [
            self._2nd_level_dep_bundle.get_major_dependency_descriptor()
        ]

        self._update_env("updating_included_app")

        # Reload env
        env = self._get_env("updating_included_app")

        # The new version of the app should reside inside common_apps.yml
        _, file_path = env.find_location_for_framework("tk-framework-test_v1.x.x")
        self.assertEqual(os.path.basename(file_path), "common_apps.yml")

        # Also, its dependency should now be picked up from the common_apps.yml file.
        _, file_path = env.find_location_for_framework(
            "tk-framework-2nd-level-dep_v1.x.x"
        )
        self.assertEqual(os.path.basename(file_path), "common_apps.yml")
