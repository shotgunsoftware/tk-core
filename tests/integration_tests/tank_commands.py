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
from tank.util import is_linux, is_macos, is_windows, filesystem
from tank.util import yaml_cache, zip

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
        cls.project = cls.create_or_update_project("TankCommandsTest", {})
        cls.asset = cls.create_or_update_entity(
            "Asset", "Test", {"project": cls.project, "sg_asset_type": "Prop"}
        )
        cls.step = cls.sg.find_one("Step", [["code", "is", "Model"]], ["short_name"])
        cls.task = cls.create_or_update_entity(
            "Task",
            "Test",
            {"entity": cls.asset, "step": cls.step, "project": cls.project},
        )

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

    def test_03_01_setup_project_from_zip_file(self):
        """
        Setups the project.
        """
        self.remove_files(self.pipeline_location)

        zipped_config_location = os.path.join(self.temp_dir, "zipped_config.zip")
        zip.zip_file(self.simple_config_location, zipped_config_location)
        self.tank_setup_project(
            self.shared_core_location,
            zipped_config_location,
            self.local_storage["code"],
            self.project["id"],
            "tankcommandtest",
            self.pipeline_location,
            force=True,
        )

    def test_03_02_setup_project_from_app_store(self):
        """
        Setups the project.
        """
        self.remove_files(self.pipeline_location)

        self.tank_setup_project(
            self.shared_core_location,
            "tk-config-testing",
            None,
            self.project["id"],
            "tankcommandtest",
            self.pipeline_location,
            force=True,
        )

    def test_03_03_setup_project_from_git(self):
        """
        Setups the project.
        """
        self.remove_files(self.pipeline_location)

        self.tank_setup_project(
            self.shared_core_location,
            "https://github.com/shotgunsoftware/tk-config-testing.git",
            None,
            self.project["id"],
            "tankcommandtest",
            self.pipeline_location,
            force=True,
        )

    def test_03_04_setup_project_from_local_config(self):
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

    def test_04_list_actions_for_project_with_shared_core(self):
        """
        Ensures that running the tank command when there is a site-wide Primary
        configurations will be able to match the project nonetheless.
        """
        self.run_tank_cmd(self.shared_core_location, None, context=self.project)

    def test_05_tank_updates(self):
        """
        Runs tank updates on the project.
        """
        output = self.run_tank_cmd(
            self.pipeline_location, "updates", user_input=("y", "a")
        )
        self.assertRegex(output, r"(.*) (.*) was updated from (.*) to (.*)")
        self.assertRegex(output, r"(.*) .* was updated from .* to .*")

    def test_06_install_engine(self):
        """
        Runs tank install on the project.
        """
        output = self.run_tank_cmd(
            self.pipeline_location,
            "install_engine",
            extra_cmd_line_arguments=["project", "tk-maya"],
        )
        self.assertRegex(output, r"Engine Installation Complete!")

    def test_07_install_app(self):
        """
        Runs tank install_app on the project.
        """
        output = self.run_tank_cmd(
            self.pipeline_location,
            "install_app",
            extra_cmd_line_arguments=["project", "tk-maya", "tk-multi-launchapp"],
        )
        self.assertRegex(output, r"App Installation Complete!")

    def test_08_app_info(self):
        """
        Runs tank app_info on the project.
        """
        output = self.run_tank_cmd(self.pipeline_location, "app_info")
        self.assertEqual(
            re.findall("App tk-multi-launchapp", output),
            ["App tk-multi-launchapp", "App tk-multi-launchapp"],
        )

    def test_09_cache_yaml(self):
        """
        Runs tank cache_yaml on the project.
        """
        # Strip the test folder, as it contains yaml files which the cache_yaml
        # command will try to cache. The problem with those files is that some
        # of them are purposefully corrupted so they will crash the caching.
        shutil.rmtree(os.path.join(self.pipeline_location, "install", "core", "tests"))
        self.run_tank_cmd(self.pipeline_location, "cache_yaml")

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
        Runs tank validate on the project.
        """
        output = self.run_tank_cmd(self.pipeline_location, "validate")
        if "ERROR:" in output:
            raise ValueError("Getting validation errors.")
        else:
            self.assertRegex(output, r"Validating Engine project / tk-maya...")
            self.assertRegex(
                output, r"Validating project / tk-maya / tk-multi-launchapp..."
            )
            self.assertRegex(
                output,
                r"The following templates are not being used directly in any environments:",
            )
            self.assertRegex(
                output,
                r"The following hooks are not being used directly in any environments:",
            )

    def test_11_tank_core(self):
        """
        Runs tank core on the project.
        """
        output = self.run_tank_cmd(self.pipeline_location, "core", user_input=("y"))
        # Since we are using a core branch we can't do a core update.
        self.assertRegex(
            output,
            r"You are currently running version HEAD of the Shotgun Pipeline Toolkit",
        )
        self.assertRegex(
            output, r"No need to update the Toolkit Core API at this time!"
        )

    def test_12_upgrade_folders(self):
        """
        Runs tank upgrade_folders on the project.
        """
        output = self.run_tank_cmd(self.pipeline_location, "upgrade_folders")
        self.assertRegex(
            output, r"Looks like syncing is already turned on! Nothing to do!"
        )

    def _get_expected_folders(self):
        """
        Returns the list of folders that are expected to be created when we run
        tank folders/preview_folders with the task created during setUpClass.
        """
        return set(
            [
                path.replace("/", os.path.sep)
                for path in [
                    "/tankcommandtest",
                    "/tankcommandtest/scenes",
                    "/tankcommandtest/sequences",
                    "/tankcommandtest/reference",
                    "/tankcommandtest/reference/artwork",
                    "/tankcommandtest/reference/footage",
                    "/tankcommandtest/assets",
                    "/tankcommandtest/assets/Prop",
                    "/tankcommandtest/assets/Prop/Test",
                    "/tankcommandtest/assets/Prop/Test/{0}".format(
                        self.step["short_name"]
                    ),
                    "/tankcommandtest/assets/Prop/Test/{0}/out".format(
                        self.step["short_name"]
                    ),
                    "/tankcommandtest/assets/Prop/Test/{0}/images".format(
                        self.step["short_name"]
                    ),
                    "/tankcommandtest/assets/Prop/Test/{0}/publish".format(
                        self.step["short_name"]
                    ),
                    "/tankcommandtest/assets/Prop/Test/{0}/review".format(
                        self.step["short_name"]
                    ),
                    "/tankcommandtest/assets/Prop/Test/{0}/work".format(
                        self.step["short_name"]
                    ),
                    "/tankcommandtest/assets/Prop/Test/{0}/work/snapshots".format(
                        self.step["short_name"]
                    ),
                ]
            ]
        )

    def test_13_cleanup_path_cache(self):
        """
        Cleans up the path cache and filesystem locations so we don't get data from
        previous test runs.
        """

        # Delete all filesystem location from previous test runs to not confuse
        # path cache related tests.
        self.local_storage["path"]
        for fsl in self.sg.find(
            "FilesystemLocation", [["project", "is", self.project]]
        ):
            self.sg.delete(fsl["type"], fsl["id"])

        # Remove any files from disk to not confuse the path cache related tests.
        if os.path.exists(self.local_storage["path"]):
            filesystem.safe_delete_folder(self.local_storage["path"])

        os.makedirs(self.local_storage["path"])

        output = self.run_tank_cmd(
            self.pipeline_location,
            "synchronize_folders",
            extra_cmd_line_arguments=["--full"],
        )
        self.assertRegex(output, r"Doing a full sync.")
        self.assertRegex(output, r"Local folder information has been synchronized.")

    def _parse_filenames(self, output):
        """
        Extract all the lines that start with " - ", which are all file names.

        :param str output: tank command text output

        :returns: Set of file paths minus the local storage path.
        """
        # Validate that folders from the output are the expected ones
        if is_windows():
            output = output.split("\r\n")
        else:
            output = output.split("\n")

        folders = []

        for line in output:
            match = re.match("^ - (.*)$", line)
            if match is not None:
                folders.append(match.groups()[0])

        return set([item.replace(self.local_storage["path"], "") for item in folders])

    def test_14_preview_folders(self):
        """
        Ensure preview folders returns the right folders to be created.
        """
        output = self.run_tank_cmd(
            self.pipeline_location, "preview_folders", context=self.task
        )

        expected_folders = self._get_expected_folders()

        # Validate preview_folders output
        self.assertRegex(
            output, "In total, %s folders were processed." % len(expected_folders)
        )
        self.assertRegex(
            output, r"Note - this was a preview and no actual folders were created."
        )
        self.assertEqual(expected_folders, self._parse_filenames(output))

    def test_15_folders(self):
        """
        Ensure folders get created properly.
        """
        fsl = self.sg.find("FilesystemLocation", [["project", "is", self.project]])
        self.assertEqual(len(fsl), 0)

        output = self.run_tank_cmd(self.pipeline_location, "folders", context=self.task)

        # Validate that folders from the output are the expected ones
        expected_folders = self._get_expected_folders()

        # Validate preview_folders output
        self.assertRegex(
            output, "In total, %s folders were processed." % len(expected_folders)
        )
        self.assertEqual(expected_folders, self._parse_filenames(output))

        fsl = self.sg.find("FilesystemLocation", [["project", "is", self.project]])
        # 3 Filesystem Locations exist.
        # One for the project
        # One for the asset
        # One for the step.
        self.assertEqual(len(fsl), 3)

    def test_16_unregister_folders_entity(self):
        """
        Ensure running tank unregister_folder on an asset will only unregister the asse
        and step folders.
        """
        output = self.run_tank_cmd(
            self.pipeline_location,
            "unregister_folders",
            context=self.asset,
            user_input=["Yes"],
        )

        expected_folders = set(
            [
                "/tankcommandtest/assets/Prop/Test".replace("/", os.path.sep),
                "/tankcommandtest/assets/Prop/Test/{0}".replace(
                    "/", os.path.sep
                ).format(self.step["short_name"]),
            ]
        )
        self.assertRegex(output, r"Unregister complete. 2 paths were unregistered.")
        self.assertEqual(expected_folders, self._parse_filenames(output))

        fsl = self.sg.find("FilesystemLocation", [["project", "is", self.project]])
        self.assertEqual(len(fsl), 1)

    def test_17_unregister_folders_all(self):
        """
        Ensure unregistering folders without any param will clear all folders.
        """
        output = self.run_tank_cmd(self.pipeline_location, "folders", context=self.task)

        output = self.run_tank_cmd(
            self.pipeline_location,
            "unregister_folders",
            extra_cmd_line_arguments=("--all",),
            user_input=["Yes"],
        )
        expected_folders = set(
            [
                "/tankcommandtest".replace("/", os.path.sep),
                "/tankcommandtest/assets/Prop/Test".replace("/", os.path.sep),
                "/tankcommandtest/assets/Prop/Test/{0}".replace(
                    "/", os.path.sep
                ).format(self.step["short_name"]),
            ]
        )
        self.assertRegex(output, r"Unregister complete. 3 paths were unregistered.")
        self.assertEqual(expected_folders, self._parse_filenames(output))

        fsl = self.sg.find("FilesystemLocation", [["project", "is", self.project]])
        self.assertEqual(fsl, [])


if __name__ == "__main__":
    ret_val = unittest2.main(failfast=True, verbosity=2)
