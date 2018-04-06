# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
This test makes sure that various tank command operations do not fail.
"""

from __future__ import print_function

import unittest2
from mock import Mock, patch
import os
import sys

from sgtk_integration_test import SgtkIntegrationTest

import sgtk

REPO_ROOT = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

# Set up logging
sgtk.LogManager().initialize_base_file_handler("offline_workflow")
sgtk.LogManager().initialize_custom_handler()

logger = sgtk.LogManager.get_logger(__name__)


class TankCommands(SgtkIntegrationTest):

    OFFLINE_WORKFLOW_TEST = "offline_workflow_test"

    def setUp(self):
        self.site_config_location = os.path.join(self.temp_dir, "site")
        self.legacy_bootstrap_core = os.path.join(self.temp_dir, "bootstrap")

    def test_01_setup_legacy_bootstrap_core(self):

        if sys.platform == "darwin":
            path_param = "config_path_mac"
        elif sys.platform == "win32":
            path_param = "config_path_win"
        elif sys.platform.startswith("linux"):
            path_param = "config_path_linux"

        cw = sgtk.bootstrap.configuration_writer.ConfigurationWriter(
            sgtk.util.ShotgunPath.from_current_os_path(self.legacy_bootstrap_core),
            self.sg
        )

        cw.ensure_project_scaffold()

        install_core_folder = os.path.join(self.legacy_bootstrap_core, "install", "core")
        os.makedirs(install_core_folder)

        cw.write_shotgun_file(Mock(get_path=lambda: "does_not_exist"))
        cw.write_install_location_file()

        sgtk.util.filesystem.copy_folder(
            REPO_ROOT, install_core_folder, skip_list=[".git", "docs", "tests"]
        )
        cw.create_tank_command()

        params = {
            "auto_path": True,
            "config_uri": "tk-config-site",
            "project_folder_name": "site",
            "project_id": None,
            path_param: self.site_config_location,
        }
        setup_project = sgtk.get_command("setup_project")
        setup_project.set_logger(logger)

        sgtk.set_authenticated_user(self.user)

        with patch(
            "tank.pipelineconfig_utils.resolve_all_os_paths_to_core",
            return_value=sgtk.util.ShotgunPath.from_current_os_path(
                self.legacy_bootstrap_core
            ).as_system_dict()
        ):
            setup_project.execute(params)


if __name__ == "__main__":
    ret_val = unittest2.main(failfast=True, verbosity=2)
