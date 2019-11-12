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
import re
import sys
import shutil

import unittest2
from mock import Mock, patch
from tank.util import is_linux, is_macos, is_windows
from tank.util import yaml_cache

from sgtk_integration_test import SgtkIntegrationTest

import sgtk

logger = sgtk.LogManager.get_logger(__name__)


class TankCommands(SgtkIntegrationTest):
    @classmethod
    def setUpClass(cls):
        super(TankCommands, cls).setUpClass()

        cls.site_config_location = os.path.join(cls.temp_dir, "site")
        cls.shared_core_location = os.path.join(cls.temp_dir, "shared")
        cls.legacy_bootstrap_core = os.path.join(cls.temp_dir, "bootstrap")
        cls.simple_config_location = os.path.join(
            os.path.dirname(__file__), "data", "simple_config"
        )
        cls.pipeline_location = os.path.join(cls.temp_dir, "pipeline")

        # Create a sandbox project for this this suite to run under.
        cls.project = cls.create_or_find_project("TankCommandsTest", {})

    def test_01_setup_legacy_bootstrap_core(self):
        """
        Sets up a site-wide configuration like Shotgun Desktop 1.3.6 used to do so we
        can make sure it doesn't get broken by more recent versions of tk-core.
        """
        self.remove_files(self.legacy_bootstrap_core, self.site_config_location)

        if is_macos():
            path_param = "config_path_mac"
        elif is_windows():
            path_param = "config_path_win"
        elif is_linux():
            path_param = "config_path_linux"

        cw = sgtk.bootstrap.configuration_writer.ConfigurationWriter(
            sgtk.util.ShotgunPath.from_current_os_path(self.legacy_bootstrap_core),
            self.sg,
        )

        # Activate the core.
        cw.ensure_project_scaffold()

        install_core_folder = os.path.join(
            self.legacy_bootstrap_core, "install", "core"
        )
        os.makedirs(install_core_folder)

        cw.write_shotgun_file(Mock(get_path=lambda: "does_not_exist"))
        cw.write_install_location_file()

        sgtk.util.filesystem.copy_folder(
            self.tk_core_repo_root,
            install_core_folder,
            skip_list=[".git", "docs", "tests"],
        )
        cw.create_tank_command()

        # Setup the site config in the legacy auto_path mode that the Desktop used.
        params = {
            "auto_path": True,
            "config_uri": os.path.join(
                os.path.dirname(__file__), "data", "site_config"
            ),
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
            ).as_system_dict(),
        ):
            setup_project.execute(params)

    def test_02_share_site_core(self):
        """
        Shares the site config's core.
        """
        self.remove_files(self.shared_core_location)

        self.run_tank_cmd(
            self.site_config_location,
            "share_core",
            extra_cmd_line_arguments=(self.shared_core_location,) * 3,
            user_input=("y",),
        )

    def test_03_setup_project_from_site_core(self):
        """
        Setups the project.
        """
        self.remove_files(self.pipeline_location)

        self.tank_setup_project(
            self.shared_core_location,
            self.simple_config_location,
            self.local_storage["code"],
            self.project["id"],
            "tankcommandtest",
            self.pipeline_location,
            force=True,
        )

    @unittest2.skipIf(
        sys.version_info[0] > 2, "shell engine is not Python 3 compatible."
    )
    def test_04_list_actions_for_project_with_shared_core(self):
        """
        Ensures that running the tank command when there is a site-wide Primary
        configurations will be able to match the project nonetheless.
        """
        self.run_tank_cmd(
            self.shared_core_location, None, ("Project", self.project["id"])
        )

    def test_05_tank_updates(self):
        """
        Runs tank object on the project.
        """
        output = self.run_tank_cmd(
            self.pipeline_location, "updates", user_input=("y", "a")
        )
        self.assertRegex(output, r"(.*) (.*) was updated from (.*) to (.*)")
        self.assertRegex(output, r"(.*) .* was updated from .* to .*")

    def test_06_install_engine(self):
        """
        Runs tank object on the project.
        """
        output = self.run_tank_cmd(
            self.pipeline_location,
            "install_engine",
            extra_cmd_line_arguments=["project", "tk-maya"],
        )
        self.assertRegex(output, r"Engine Installation Complete!")

    def test_07_install_app(self):
        """
        Runs tank object on the project.
        """
        output = self.run_tank_cmd(
            self.pipeline_location,
            "install_app",
            extra_cmd_line_arguments=["project", "tk-maya", "tk-multi-launchapp"],
        )
        self.assertRegex(output, r"App Installation Complete!")

    def test_08_app_info(self):
        """
        Runs tank object on the project.
        """
        output = self.run_tank_cmd(self.pipeline_location, "app_info")
        self.assertEqual(
            re.findall("App tk-multi-launchapp", output),
            ["App tk-multi-launchapp", "App tk-multi-launchapp"],
        )

    def test_09_cache_yaml(self):
        """
        Runs tank object on the project.
        """
        # Strip the test folder, as it contains yaml files which the cache_yaml
        # command will try to cache. The problem with those files is that some
        # of them are purposefully corrupted so they will crash the caching.
        shutil.rmtree(os.path.join(self.pipeline_location, "install", "core", "tests"))
        output = self.run_tank_cmd(self.pipeline_location, "cache_yaml")

        yaml_cache.g_yaml_cache = yaml_cache.YamlCache()
        self.assertEqual(yaml_cache.g_yaml_cache.get_cached_items(), [])
        # This should trigger a load of the cache.
        sgtk.sgtk_from_path(self.pipeline_location)
        self.assertNotEqual(yaml_cache.g_yaml_cache.get_cached_items(), [])

        # Extract all the file names from the cache, but strip the pipeline location from the paths.
        items = set(
            [
                item.path.replace(self.pipeline_location, "")
                for item in yaml_cache.g_yaml_cache.get_cached_items()
            ]
        )

        expected_items = set(
            [
                path.replace("/", os.path.sep)
                for path in [
                    "/config/core/core_api.yml",
                    "/config/core/install_location.yml",
                    "/config/core/pipeline_configuration.yml",
                    "/config/core/roots.yml",
                    "/config/core/shotgun.yml",
                    "/config/env/project.yml",
                    # Do not check for versions of bundles pulled from the appstore as they will change
                    # over time.
                    "/install/core/info.yml",
                ]
            ]
        )

        self.assertTrue(
            expected_items.issubset(items),
            "{0} should be a subset of {1}".format(
                sorted(expected_items), sorted(items)
            ),
        )

    def test_10_validate(self):
        """
        Runs tank object on the project.
        """
        output = self.run_tank_cmd(self.pipeline_location, "validate")
        if "ERROR:" in output:
            raise ValueError('Getting validation errors.')
        else:
            self.assertRegex(output, r"Validating Engine project / tk-maya...")
            self.assertRegex(output, r"Validating project / tk-maya / tk-multi-launchapp...")
            self.assertRegex(output, r"The following templates are not being used directly in any environments:")
            self.assertRegex(output, r"The following hooks are not being used directly in any environments:")


if __name__ == "__main__":
    ret_val = unittest2.main(failfast=True, verbosity=2)
