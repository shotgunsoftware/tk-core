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

import os
import fnmatch
import stat
import sys
from mock import patch
import sgtk
from shutil import copytree

from tank_test.tank_test_base import setUpModule # noqa
from tank_test.tank_test_base import temp_env_var
from tank_test.tank_test_base import TankTestBase


# Copied from Python 2.7's source code.
def ignore_patterns(*patterns):
    """Function that can be used as copytree() ignore parameter.

    Patterns is a sequence of glob-style patterns
    that are used to exclude files"""
    def _ignore_patterns(path, names):
        ignored_names = []
        for pattern in patterns:
            ignored_names.extend(fnmatch.filter(names, pattern))
        return set(ignored_names)
    return _ignore_patterns


class TestBackups(TankTestBase):
    def setUp(self):
        super(TestBackups, self).setUp()

        pathHead, pathTail = os.path.split(__file__)
        self._core_repo_path=os.path.join(pathHead,"..", "..")
        self._temp_test_path=os.path.join(pathHead, "..", "fixtures", "bootstrap_tests", "test_backups")
        if sys.platform == "win32": # On Windows, filenames in temp path are too long for straight copy ...
            core_copy_path=os.path.join(self.tank_temp, "tk-core-copy")
            if not os.path.exists(core_copy_path):
                # ... so avoid copying ignore folders to avoid errors when copying the core repo
                copytree(self._core_repo_path, core_copy_path, ignore=ignore_patterns('tests', 'docs', 'coverage_html_report')) 
            self._core_repo_path = core_copy_path

    def test_cleanup(self):
        """
        Ensures that after a successful update the backup folder created by the
        update process is properly deleted 
        """
        resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="backup_tests"
        )
        with temp_env_var(SGTK_REPO_ROOT=self._core_repo_path):
            config = resolver.resolve_configuration(
                {"type": "dev", "name": "backup_tests", "path": self._temp_test_path}, self.tk.shotgun
            )
            self.assertIsInstance(config, sgtk.bootstrap.resolver.CachedConfiguration)
            config_root_path = config.path.current_os

            # Update the configuration
            config.update_configuration()
            core_install_backup_path = os.path.join(config_root_path, "install", "core.backup")
            # check that there are no directory items in core backup folder other than then placeholder file
            self.assertEqual(os.listdir(core_install_backup_path), ['placeholder'])
            config_install_backup_path = os.path.join(config_root_path, "install", "config.backup")
            # check that there are no directory items in config backup folder other than then placeholder file
            self.assertEqual(os.listdir(config_install_backup_path), ['placeholder'])

            # Update a second time and check that backup was cleaned up again
            config.update_configuration()
            self.assertEqual(os.listdir(core_install_backup_path), ['placeholder'])
            self.assertEqual(os.listdir(config_install_backup_path), ['placeholder'])

    def test_cleanup_with_fail(self):
        """
        Ensures that after an update with a cleanup failure, the succeeding update 
        process completes smoothly
        """
        resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="backup_tests_with_fail"
        )
        with temp_env_var(SGTK_REPO_ROOT=self._core_repo_path):
            config = resolver.resolve_configuration(
                {"type": "dev", "name": "backup_tests_with_fail", "path": self._temp_test_path}, self.tk.shotgun
            )
            self.assertIsInstance(config, sgtk.bootstrap.resolver.CachedConfiguration)
            config_root_path = config.path.current_os
            core_install_backup_path = os.path.join(config_root_path, "install", "core.backup")

            # First update, no backup
            config.update_configuration()

            def dont_cleanup_backup_folders(self, config, core):
                self.config_backup_folder_path = config
                self.core_backup_folder_path = core

            # Update the configuration, but don't clean up backups
            with patch.object(sgtk.bootstrap.resolver.CachedConfiguration, '_cleanup_backup_folders', new=dont_cleanup_backup_folders):
                config.update_configuration()
                config_backup_folder_path = config.config_backup_folder_path
                core_backup_folder_path = config.core_backup_folder_path
                in_use_file_name = os.path.join(core_backup_folder_path, "test.txt")
            
            # Create a file
            with open(in_use_file_name, "w") as f:
                f.write("Test")
                config._cleanup_backup_folders(config_backup_folder_path, core_backup_folder_path)

            if sys.platform == "win32":
                # check that the backup folder was left behind, it is one of the 2 items, the cleanup failed
                self.assertEqual(2, len(os.listdir(core_install_backup_path)))  # ['placeholder', core_backup_folder_path]
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
                self.assertEqual(2, len(os.listdir(core_install_backup_path))) # ['placeholder', core_backup_folder_path]
            else:
                self.assertEqual(os.listdir(core_install_backup_path), ['placeholder'])
            self.assertEqual(os.listdir(config_install_backup_path), ['placeholder'])

    def test_cleanup_read_only(self):
        """
        Ensures that backup cleanup will succeed even with read only folder items
        """
        resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="backup_tests_read_only"
        )
        with temp_env_var(SGTK_REPO_ROOT=self._core_repo_path):
            config = resolver.resolve_configuration(
                {"type": "dev", "name": "backup_tests_read_only", "path": self._temp_test_path}, self.tk.shotgun
            )
            self.assertIsInstance(config, sgtk.bootstrap.resolver.CachedConfiguration)
            config_root_path = config.path.current_os
            core_install_backup_path = os.path.join(config_root_path, "install", "core.backup")
            config_install_backup_path = os.path.join(config_root_path, "install", "config.backup")

            # First update, no backup
            config.update_configuration()
            
            def dont_cleanup_backup_folders(self, config, core):
                self.config_backup_folder_path = config
                self.core_backup_folder_path = core

            with patch.object(sgtk.bootstrap.resolver.CachedConfiguration, '_cleanup_backup_folders', new=dont_cleanup_backup_folders):
                # Update the configuration, but don't clean up backups in order to ...
                config.update_configuration()
                config_backup_folder_path = config.config_backup_folder_path
                core_backup_folder_path = config.core_backup_folder_path
                read_only_file_name = os.path.join(core_backup_folder_path, "test.txt")

            # ... create a read only file ...
            with open(read_only_file_name, "w") as f:
                f.write("Test")
            file_permissions = os.stat(read_only_file_name)[stat.ST_MODE]
            os.chmod(read_only_file_name, file_permissions & ~stat.S_IWRITE)
            if sys.platform == "win32":
                # ... and a read only folder
                folder_permissions = os.stat(config_install_backup_path)[stat.ST_MODE]
                os.chmod(config_install_backup_path, folder_permissions & ~stat.S_IWRITE)

            # Now try to clean up the backup folders with read-only file
            config._cleanup_backup_folders(config_backup_folder_path, core_backup_folder_path)

            # Verify that backup folders were cleaned up
            self.assertEqual(os.listdir(core_install_backup_path), ['placeholder'])
            self.assertEqual(os.listdir(config_install_backup_path), ['placeholder'])
