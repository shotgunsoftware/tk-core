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

import logging

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    TankTestBase,
)

from sgtk.pipelineconfig_utils import get_core_descriptor

from tank_test.mock_appstore import patch_app_store


# We need to patch the currently running core API version, as this will
# likely be HEAD otherwise when running tests.
@mock.patch(
    "tank.pipelineconfig_utils.get_currently_running_api_version",
    return_value="v0.18.91",
)
# Since we are mocking the app store core releases, there won't be any release notes,
# so we should mock those as well, otherwise it will fail
@mock.patch(
    "tank.commands.core_upgrade.TankCoreUpdater.get_release_notes",
    return_value=("description", "url"),
)
# We're mocking _install_core so that it does nothing. We are only
# testing that it can update the core_api.yml.
@mock.patch("tank.commands.core_upgrade.TankCoreUpdater._install_core")
# Need to set the path to the cache config, this is done in the method.
@mock.patch("tank.pipelineconfig_utils.get_path_to_current_core")
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
        pass
    @mock.patch(
        "tank.descriptor.descriptor.Descriptor.is_immutable", return_value=True,
    )
    def test_immutable_config_core_update_core_api_yaml(
        self, _mock_is_immutable, mock_config_path, *_
    ):
        pass
    @mock.patch(
        "tank.descriptor.descriptor.Descriptor.is_dev", return_value=True,
    )
    @mock.patch("tank.descriptor.descriptor.Descriptor.get_path")
    def test_dev_config_core_update_core_api_yaml(
        self, mock_get_path, _mock_is_dev, mock_config_path, *_
    ):
        pass
