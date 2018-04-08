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

import os
import sys

import unittest2
from mock import Mock, patch

from sgtk_integration_test import SgtkIntegrationTest

import sgtk

logger = sgtk.LogManager.get_logger(__name__)


class TankCommands(SgtkIntegrationTest):

    OFFLINE_WORKFLOW_TEST = "offline_workflow_test"

    @classmethod
    def setUpClass(cls):
        super(TankCommands, cls).setUpClass()

        cls.site_config_location = os.path.join(cls.temp_dir, "site")
        cls.shared_core_location = os.path.join(cls.temp_dir, "shared")
        cls.legacy_bootstrap_core = os.path.join(cls.temp_dir, "bootstrap")
        cls.simple_config_location = os.path.join(os.path.dirname(__file__), "data", "simple_config")

        # Create a sandbox project for this this suite to run under.
        cls.project = cls.create_or_find_project("TankCommandsTest", {})

    def test_01_setup_legacy_bootstrap_core(self):
        """
        Sets up a site-wide configuration like Shotgun Desktop 1.3.6 used to do so we
        can make sure it doesn't get broken by more recent versions of tk-core.
        """
        self.remove_files(self.legacy_bootstrap_core, self.site_config_location)

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

        # Activate the core.
        cw.ensure_project_scaffold()

        install_core_folder = os.path.join(self.legacy_bootstrap_core, "install", "core")
        os.makedirs(install_core_folder)

        cw.write_shotgun_file(Mock(get_path=lambda: "does_not_exist"))
        cw.write_install_location_file()

        sgtk.util.filesystem.copy_folder(
            self.tk_core_repo_root, install_core_folder, skip_list=[".git", "docs", "tests"]
        )
        cw.create_tank_command()

        # Setup the site config in the legacy auto_path mode that the Desktop used.
        params = {
            "auto_path": True,
            "config_uri": os.path.join(os.path.dirname(__file__), "data", "site_config"),
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

    def test_02_share_site_core(self):
        """
        Shares the site config's core.
        """
        self.remove_files(self.shared_core_location)

        self.run_tank_cmd(
            self.site_config_location,
            ("share_core",) + (self.shared_core_location,) * 3,
            user_input=("y",)
        )

    def test_03_setup_project_from_site_core(self):
        """
        Setups the project.
        """
        pipeline_location = os.path.join(self.temp_dir, "pipeline")
        self.tank_setup_project(
            self.shared_core_location,
            self.simple_config_location,
            self.local_storage["code"],
            self.project["id"],
            "tankcommandtest",
            pipeline_location,
            force=True
        )

    def test_04_list_actions_for_project_with_shared_core(self):
        """
        Ensures that running the tank command when there is a site-wide Primary
        configurations will be able to match the project nonetheless.
        """
        self.run_tank_cmd(
            self.shared_core_location,
            ("Project", str(self.project["id"]))
        )


if __name__ == "__main__":
    ret_val = unittest2.main(failfast=True, verbosity=2)
