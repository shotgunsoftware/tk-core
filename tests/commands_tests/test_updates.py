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
        pass
    def test_environment(self):
        pass
    def test_simple_update(self):
        pass
class TestIncludeUpdates(TankTestBase):
    """
    Tests updates to bundle within includes.
    """

    def setUp(self):
        pass
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
