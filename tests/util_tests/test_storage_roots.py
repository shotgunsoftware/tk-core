# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import ShotgunTestBase

from tank.errors import TankError
from tank.util import ShotgunPath
from tank.util import StorageRoots


class TestStorageRoots(ShotgunTestBase):
    """
    tests the ShotgunPath class
    """

    def setUp(self):

        super().setUp()

        # ---- mock some local storages

        self.primary_storage = {
            "type": "LocalStorage",
            "id": 1,
            "code": "primary",
            "mac_path": "/tmp/primary",
            "windows_path": "X:\\tmp\\primary",
            "linux_path": "/tmp/primary",
        }
        self.add_to_sg_mock_db([self.primary_storage])

        self.work_storage = {
            "type": "LocalStorage",
            "id": 2,
            "code": "work",
            "mac_path": "/tmp/work",
            "windows_path": "X:\\tmp\\work",
            "linux_path": "/tmp/work",
        }
        self.add_to_sg_mock_db([self.work_storage])

        self.data_storage = {
            "type": "LocalStorage",
            "id": 3,
            "code": "data",
            "mac_path": "/tmp/data",
            "windows_path": "X:\\tmp\\data",
            "linux_path": "/tmp/data",
        }
        self.add_to_sg_mock_db([self.data_storage])

        # ---- paths/metadata defined by the fixtures

        # this folder houses all storage root-specific fixtures
        roots_fixtures_folder = os.path.join(
            self.fixtures_root, "util", "storage_roots"
        )

        # no roots
        self._no_roots_config_folder = os.path.join(
            roots_fixtures_folder, "no_roots", "config"
        )
        # these tests assume the metadata matches the corresponding fixture roots
        self._no_roots_metadata = {}

        # empty roots
        self._empty_roots_config_folder = os.path.join(
            roots_fixtures_folder, "empty_roots", "config"
        )
        # these tests assume the metadata matches the corresponding fixture roots
        self._empty_roots_metadata = {}

        # single root
        self._single_root_config_folder = os.path.join(
            roots_fixtures_folder, "single_root", "config"
        )
        # these tests assume the metadata matches the corresponding fixture roots
        self._single_root_metadata = {
            "primary": {
                "linux_path": "/tmp/primary",
                "mac_path": "/tmp/primary",
                "windows_path": "X:\\tmp\\primary",
            }
        }

        # multiple roots
        self._multiple_roots_config_folder = os.path.join(
            roots_fixtures_folder, "multiple_roots", "config"
        )
        # these tests assume the metadata matches the corresponding fixture roots
        self._multiple_roots_metadata = {
            "work": {
                "linux_path": "/tmp/work",
                "mac_path": "/tmp/work",
                "windows_path": "X:\\tmp\\work",
                "default": True,
            },
            "data": {
                "linux_path": "/tmp/data",
                "mac_path": "/tmp/data",
                "windows_path": "X:\\tmp\\data",
            },
            "foobar": {
                "linux_path": "/tmp/foobar",
                "mac_path": "/tmp/foobar",
                "windows_path": "X:\\tmp\\foobar",
            },
        }

        # corrupt roots
        self._corrupt_roots_config_folder = os.path.join(
            roots_fixtures_folder, "corrupt_roots", "config"
        )

        # setup a temp folder for reading/writing configs
        self._config_folder = os.path.join(
            self.tank_temp, "test_storage_roots", "config"
        )
        if not os.path.exists(self._config_folder):
            os.makedirs(self._config_folder)

    def test_storage_roots_file_exists(self):
        pass
    def test_storage_roots_from_config(self):
        pass
    def test_storage_roots_from_metadata(self):
        pass
    def test_storage_roots_write(self):
        pass
    def test_storage_roots_as_shotgun_paths(self):
        pass
    def test_storage_roots_default(self):
        pass
    def test_storage_roots_default_path(self):
        pass
    def test_storage_roots_metadata(self):
        pass
    def test_storage_roots_roots_file(self):
        pass
    def test_storage_roots_required_roots(self):
        pass
    def test_storage_roots_get_local_storages(self):
        pass
    def test_storage_roots_populate_defaults(self):
        pass
    def test_update_root(self):
        pass
