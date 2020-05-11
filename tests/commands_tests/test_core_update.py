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
Unit tests tank core update.
"""
from __future__ import with_statement

import logging

from tank_test.tank_test_base import TankTestBase, setUpModule  # noqa

from sgtk.pipelineconfig_utils import get_core_descriptor
from mock import patch

from tank_test.mock_appstore import patch_app_store


# We need to patch the currently running core API version, as this will
# likely be HEAD otherwise when running tests.
@patch(
    "tank.pipelineconfig_utils.get_currently_running_api_version",
    return_value="v0.18.91",
)
# Since we are mocking the app store core releases, there won't be any release notes,
# so we should mock those as well, otherwise it will fail
@patch(
    "tank.commands.core_upgrade.TankCoreUpdater.get_release_notes",
    return_value=("description", "url"),
)
# We're mocking _install_core so that it does nothing. We are only
# testing that it can update the core_api.yml.
@patch("tank.commands.core_upgrade.TankCoreUpdater._install_core",)
# Need to set the path to the cache config, this is done in the method.
@patch("tank.pipelineconfig_utils.get_path_to_current_core",)
class TestCoreUpdate(TankTestBase):
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
        self.setup_fixtures("core_update_tests", parameters={"installed_config": True})

        # This will be the core version we will update to.
        self._mock_store.add_core("v0.19.5")

    def test_installed_core_update_core_api_yaml(self, mock_config_path, *_):
        """
        Checks if the core_api.yml gets updated when running a core update command.
        We're not testing that the core actually gets copied into place and the old one
        swapped out, it's patched so that code doesn't run.
        """
        # We need to set the `pipelineconfig_utils.get_path_to_current_core` to return
        # the path to the config created by the fixtures.
        mock_config_path.return_value = self.pipeline_config_root

        # First check the current core_api.yml is in the state we expect.
        descriptor = get_core_descriptor(self.pipeline_config_root, self.tk.shotgun)
        self.assertEqual(descriptor.version, "v0.18.91")

        # Run appstore updates.
        command = self.tk.get_command("core")
        command.set_logger(logging.getLogger("/dev/null"))
        command.execute({})

        # Now check the core_api.yml has updated to the app store version.
        descriptor = get_core_descriptor(self.pipeline_config_root, self.tk.shotgun)
        self.assertEqual(descriptor.version, "v0.19.5")

    @patch(
        "tank.descriptor.descriptor.Descriptor.is_immutable", return_value=True,
    )
    def test_immutable_config_core_update_core_api_yaml(
        self, _mock_is_immutable, mock_config_path, *_
    ):
        """
        Checks that the config's core_api.yml does not get updated when the config is immutable.
        """
        # We need to set the `pipelineconfig_utils.get_path_to_current_core` to return
        # the path to the config created by the fixtures.
        mock_config_path.return_value = self.pipeline_config_root
        # Run appstore updates.
        command = self.tk.get_command("core")
        command.set_logger(logging.getLogger("/dev/null"))
        command.execute({})

        # Now we check that the config did not get updated since it is immutable
        # the version number should have stayed the same.
        descriptor = get_core_descriptor(self.pipeline_config_root, self.tk.shotgun)
        self.assertEqual(descriptor.version, "v0.18.91")

    @patch(
        "tank.descriptor.descriptor.Descriptor.is_dev", return_value=True,
    )
    @patch("tank.descriptor.descriptor.Descriptor.get_path")
    def test_dev_config_core_update_core_api_yaml(
        self, mock_get_path, _mock_is_dev, mock_config_path, *_
    ):
        """
        Checks if the core_api.yml gets updated when running a core update command, when using a dev config.
        """
        # We need to set the `pipelineconfig_utils.get_path_to_current_core` to return
        # the path to the config created by the fixtures.
        mock_config_path.return_value = self.pipeline_config_root
        # We're mocking the Descriptor.get_path as the tests run with an installed config, but we
        # want it to behave as if it was a dev descriptor config.
        # An installed config's Descriptor.get_path will return the path to the root of the
        # PipelineConfiguration location, where as a dev descriptor's get_path would return the path
        # to what would normally be the "config" folder inside the root of an installed config.
        mock_get_path.return_value = self.project_config
        # Run appstore updates.
        command = self.tk.get_command("core")
        command.set_logger(logging.getLogger("/dev/null"))
        command.execute({})

        # Now we check that the config did not get updated since it is immutable
        # the version number should have stayed the same.
        descriptor = get_core_descriptor(self.pipeline_config_root, self.tk.shotgun)
        self.assertEqual(descriptor.version, "v0.19.5")
