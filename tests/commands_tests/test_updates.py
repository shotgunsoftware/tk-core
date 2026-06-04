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

import os
import sys
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
        pass
    def test_simple_update(self):
        pass
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
        return self._update_cmd.execute({"environment_filter": env_name})

    def test_update_include(self):
        pass
    def test_update_include_with_new_framework(self):
        pass
