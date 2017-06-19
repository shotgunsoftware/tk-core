# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import with_statement

import itertools
import os
import sys
from mock import patch
import sgtk
from sgtk.util import ShotgunPath
from sgtk.bootstrap.configuration_writer import ConfigurationWriter
from shutil import copytree, ignore_patterns

from tank.descriptor import Descriptor, descriptor_uri_to_dict, descriptor_dict_to_uri, create_descriptor
from tank_test.tank_test_base import setUpModule # noqa
from tank_test.tank_test_base import temp_env_var
from tank_test.tank_test_base import TankTestBase


class TestBackups(TankTestBase):
    def setUp(self):
        super(TestBackups, self).setUp()

        self._tmp_bundle_cache = os.path.join(self.tank_temp, "bundle_cache")

    def test_cleanup(self):
        """
        Ensures that after a successful update the backup folder created by the
        update process is properly deleted 
        """
        resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="backup_tests",
            bundle_cache_fallback_paths=[self._tmp_bundle_cache]
        )
        pathHead, pathTail = os.path.split(__file__)
        core_path=os.path.join(pathHead,"..", "..")
        temp_test_path=os.path.join(pathHead, "..", "fixtures", "bootstrap_tests", "test_backups")
        core_copy_path=os.path.join(self.tank_temp, "tk-core-copy")
        copytree(core_path, core_copy_path, ignore=ignore_patterns('tests', 'docs'))
        with temp_env_var(SGTK_REPO_ROOT=temp_test_path, SGTK_CORE_REPO=core_copy_path):
            config = resolver.resolve_configuration(
                {"type": "dev", "name": "backup_tests", "path": "$SGTK_REPO_ROOT"}, self.tk.shotgun
            )
            self.assertIsInstance(config, sgtk.bootstrap.resolver.CachedConfiguration)
            config_root_path = config.path.current_os
            sg_config_dir = os.path.join(config_root_path, "config", "core")
            os.makedirs(sg_config_dir)
            sg_install_dir = os.path.join(config_root_path, "install", "core")
            os.makedirs(sg_install_dir)
            sg_config_location = os.path.join(sg_config_dir, "core_api.yml")
            with open(sg_config_location, "w") as f:
                f.write("location:\n  type: dev\n  path: $SGTK_CORE_REPO\n")

            # Update the configuration
            config.update_configuration()
            core_install_backup_path = os.path.join(config_root_path, "install", "core.backup")
            # check that there are no directory items in core backup folder other than then placeholder file
            self.assertEqual(os.listdir(core_install_backup_path), ['placeholder'])
            config_install_backup_path = os.path.join(config_root_path, "install", "config.backup")
            # check that there are no directory items in config backup folder other than then placeholder file
            self.assertEqual(os.listdir(config_install_backup_path), ['placeholder'])

            # Update a second time and check that backup was cleaned up again
            config.update_configuration(False)
            config.cleanup_backup_folders()
            self.assertEqual(os.listdir(core_install_backup_path), ['placeholder'])
            self.assertEqual(os.listdir(config_install_backup_path), ['placeholder'])

    def test_cleanup_with_fail(self):
        """
        Ensures that after an update with a cleanup failure, the succeeding update 
        process still succeeds
        """
        resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="backup_tests_with_fail",
            bundle_cache_fallback_paths=[self._tmp_bundle_cache]
        )
        pathHead, pathTail = os.path.split(__file__)
        core_path=os.path.join(pathHead,"..", "..")
        temp_test_path=os.path.join(pathHead, "..", "fixtures", "bootstrap_tests", "test_backups")
        core_copy_path=os.path.join(self.tank_temp, "tk-core-copy-with_fail")
        copytree(core_path, core_copy_path, ignore=ignore_patterns('tests', 'docs'))
        with temp_env_var(SGTK_REPO_ROOT=temp_test_path, SGTK_CORE_REPO=core_copy_path):
            config = resolver.resolve_configuration(
                {"type": "dev", "name": "backup_tests_with_fail", "path": "$SGTK_REPO_ROOT"}, self.tk.shotgun
            )
            self.assertIsInstance(config, sgtk.bootstrap.resolver.CachedConfiguration)
            config_root_path = config.path.current_os
            sg_config_dir = os.path.join(config_root_path, "config", "core")
            os.makedirs(sg_config_dir)
            sg_install_dir = os.path.join(config_root_path, "install", "core")
            os.makedirs(sg_install_dir)
            sg_config_location = os.path.join(sg_config_dir, "core_api.yml")
            with open(sg_config_location, "w") as f:
                f.write("location:\n  type: dev\n  path: $SGTK_CORE_REPO\n")

            # Update the configuration, but don't clean up backups
            config.update_configuration(False)
            core_install_backup_path = os.path.join(config_root_path, "install", "core.backup")
            in_use_file_name = os.path.join(config.core_backup_folder_path, "test.txt")
            # Create a file
            with open(in_use_file_name, "w") as f:
                f.write("Test")
            # Open the file and make it 'in use'
            with open(in_use_file_name) as f:
                config.cleanup_backup_folders()
            if sys.platform == "win32":
                # check that the backup folder was left behind, it is one of the 2 items, the cleanup failed
                self.assertEqual(2, len(os.listdir(core_install_backup_path)))  # ['placeholder', config.core_backup_folder_path]
            else:
                # on Unix, having the file open won't fail the folder removal
                self.assertEqual(os.listdir(core_install_backup_path), ['placeholder'])
            config_install_backup_path = os.path.join(config_root_path, "install", "config.backup")
            # check that there are no directory items in config backup folder other than then placeholder file
            self.assertEqual(os.listdir(config_install_backup_path), ['placeholder'])

            # Update a second time and check that the new backup was cleaned up...
            config.update_configuration()
            if sys.platform == "win32":
                # ... but the previous backup remains
                self.assertEqual(2, len(os.listdir(core_install_backup_path))) # ['placeholder', config.core_backup_folder_path]
            else:
                self.assertEqual(os.listdir(core_install_backup_path), ['placeholder'])
            self.assertEqual(os.listdir(config_install_backup_path), ['placeholder'])

