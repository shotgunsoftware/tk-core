# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

from tank import TankError
from tank.util import LocalFileStorageManager
from tank.util import is_macos, is_windows

from tank_test.tank_test_base import ShotgunTestBase, setUpModule  # noqa


class TestLocalFileStorage(ShotgunTestBase):
    """
    tests the ShotgunPath class
    """

    def setUp(self):
        super().setUp()

        # We can't assume that SHOTGUN_HOME is not set, so unset it for the tests.
        self._old_value = os.environ.get(self.SHOTGUN_HOME)
        if self._old_value:
            del os.environ[self.SHOTGUN_HOME]

    def tearDown(self):
        # Set it back if there was a value before.
        if self._old_value:
            os.environ[self.SHOTGUN_HOME] = self._old_value

        super().tearDown()

    def test_global(self):
        pass
    def test_legacy_global(self):
        pass
    def test_site(self):
        pass
    def _compute_config_root(self, project_id, plugin_id, pc_id, expected_suffix):

        for hostname in [
            "http://test.shotgunstudio.com",
            "http://test.shotgrid.autodesk.com",
        ]:
            path_types = [
                LocalFileStorageManager.PREFERENCES,
                LocalFileStorageManager.CACHE,
                LocalFileStorageManager.PERSISTENT,
                LocalFileStorageManager.LOGGING,
            ]

            for path_type in path_types:
                root = LocalFileStorageManager.get_configuration_root(
                    hostname, project_id, plugin_id, pc_id, path_type
                )

                site_root = LocalFileStorageManager.get_site_root(hostname, path_type)

                self.assertEqual(root, os.path.join(site_root, expected_suffix))

    def test_config_root(self):
        pass
    def _compute_legacy_config_root(
        self, project_id, plugin_id, pc_id, expected_suffix
    ):

        for hostname in [
            "http://test.shotgunstudio.com",
            "http://test.shotgrid.autodesk.com",
        ]:

            path_types = [
                LocalFileStorageManager.CACHE,
                LocalFileStorageManager.PERSISTENT,
                LocalFileStorageManager.LOGGING,
            ]

            for path_type in path_types:
                root = LocalFileStorageManager.get_configuration_root(
                    hostname,
                    project_id,
                    plugin_id,
                    pc_id,
                    path_type,
                    LocalFileStorageManager.CORE_V17,
                )

                site_root = LocalFileStorageManager.get_site_root(
                    hostname, path_type, LocalFileStorageManager.CORE_V17
                )

                self.assertEqual(root, os.path.join(site_root, expected_suffix))

    def test_legacy_config_root(self):
        pass
class TestCustomRoot(ShotgunTestBase):
    def test_custom_root(self):
        pass
    def test_env_var_and_tilde(self):
        pass
