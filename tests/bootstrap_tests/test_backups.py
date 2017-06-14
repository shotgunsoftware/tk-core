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

from tank.descriptor import Descriptor, descriptor_uri_to_dict, descriptor_dict_to_uri, create_descriptor, constants
from tank_test.tank_test_base import setUpModule # noqa
from tank_test.tank_test_base import temp_env_var
from tank_test.tank_test_base import TankTestBase


class TestBackups(TankTestBase):
    def setUp(self):
        super(TestBackups, self).setUp()

        self._tmp_bundle_cache = os.path.join(self.tank_temp, "bundle_cache")
        self._resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="backup_tests",
            bundle_cache_fallback_paths=[self._tmp_bundle_cache]
        )

    def test_cleanup(self):
        """
        Ensures that after a successful update the backup folder created by the
        update process is properly deleted 
        """
        pathHead, pathTail = os.path.split(__file__)
        core_path=os.path.join(pathHead,"..", "..")
        temp_test_path=os.path.join(pathHead, "..", "fixtures", "bootstrap_tests", "test_update")
        core_copy_path=os.path.join(self.tank_temp, "tk-core-copy")
        copytree(core_path, core_copy_path, ignore=ignore_patterns('tests', 'docs'))
        with temp_env_var(SGTK_REPO_ROOT=temp_test_path):
            with temp_env_var(SGTK_CORE_REPO=core_copy_path):
                config = self._resolver.resolve_configuration(
                    {"type": "dev", "name": "backup_tests", "path": "$SGTK_REPO_ROOT"}, self.tk.shotgun
                )
                self.assertIsInstance(config, sgtk.bootstrap.resolver.CachedConfiguration)
                config_root_path = config._config_writer._path.current_os
                sg_config_dir = os.path.join(config_root_path, "config", "core")
                os.makedirs(sg_config_dir)
                sg_install_dir = os.path.join(config_root_path, "install", "core")
                os.makedirs(sg_install_dir)
                sg_config_location = os.path.join(sg_config_dir, constants.CONFIG_CORE_DESCRIPTOR_FILE)
                with open(sg_config_location, "w") as f:
                    f.write("location:\n  type: dev\n  path: $SGTK_CORE_REPO\n")

                # Update the configuration
                config.update_configuration()
                core_install_backup_path = os.path.join(config_root_path, "install", "core.backup")
                for root, dirs, files in os.walk(core_install_backup_path, topdown=False):
                    # check core backup folder was not removed
                    self.assertEqual(0, len(dirs))
                config_install_backup_path = os.path.join(config_root_path, "install", "config.backup")
                for root, dirs, files in os.walk(config_install_backup_path, topdown=False):
                    # check core config backup folder was removed
                    self.assertEqual(0, len(dirs))

                # Update a second time and check that backup was cleaned up again
                config.update_configuration()
                core_install_backup_path = os.path.join(config_root_path, "install", "core.backup")
                for root, dirs, files in os.walk(core_install_backup_path, topdown=False):
                    self.assertEqual(0, len(dirs))
                config_install_backup_path = os.path.join(config_root_path, "install", "config.backup")
                for root, dirs, files in os.walk(config_install_backup_path, topdown=False):
                    self.assertEqual(0, len(dirs))

