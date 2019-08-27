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

from tank_test.tank_test_base import setUpModule # noqa
from tank_test.tank_test_base import ShotgunTestBase

from tank.errors import TankError
from tank.util import ShotgunPath
from tank.util import StorageRoots


class TestStorageRoots(ShotgunTestBase):
    """
    tests the ShotgunPath class
    """

    def setUp(self):

        super(TestStorageRoots, self).setUp()

        # ---- mock some local storages

        self.primary_storage = {
            "type": "LocalStorage",
            "id": 1,
            "code": "primary",
            "mac_path": "/tmp/primary",
            "windows_path": "X:\\tmp\\primary",
            "linux_path": "/tmp/primary"
        }
        self.add_to_sg_mock_db([self.primary_storage])

        self.work_storage = {
            "type": "LocalStorage",
            "id": 2,
            "code": "work",
            "mac_path": "/tmp/work",
            "windows_path": "X:\\tmp\\work",
            "linux_path": "/tmp/work"
        }
        self.add_to_sg_mock_db([self.work_storage])

        self.data_storage = {
            "type": "LocalStorage",
            "id": 3,
            "code": "data",
            "mac_path": "/tmp/data",
            "windows_path": "X:\\tmp\\data",
            "linux_path": "/tmp/data"
        }
        self.add_to_sg_mock_db([self.data_storage])

        # ---- paths/metadata defined by the fixtures

        # this folder houses all storage root-specific fixtures
        roots_fixtures_folder = os.path.join(
            self.fixtures_root,
            "util",
            "storage_roots"
        )

        # no roots
        self._no_roots_config_folder = os.path.join(
            roots_fixtures_folder,
            "no_roots",
            "config"
        )
        # these tests assume the metadata matches the corresponding fixture roots
        self._no_roots_metadata = {}

        # empty roots
        self._empty_roots_config_folder = os.path.join(
            roots_fixtures_folder,
            "empty_roots",
            "config"
        )
        # these tests assume the metadata matches the corresponding fixture roots
        self._empty_roots_metadata = {}

        # single root
        self._single_root_config_folder = os.path.join(
            roots_fixtures_folder,
            "single_root",
            "config"
        )
        # these tests assume the metadata matches the corresponding fixture roots
        self._single_root_metadata = {
            "primary": {
                "linux_path": "/tmp/primary",
                "mac_path": "/tmp/primary",
                "windows_path": "X:\\tmp\\primary"
            }
        }

        # multiple roots
        self._multiple_roots_config_folder = os.path.join(
            roots_fixtures_folder,
            "multiple_roots",
            "config"
        )
        # these tests assume the metadata matches the corresponding fixture roots
        self._multiple_roots_metadata = {
            "work": {
                "linux_path": "/tmp/work",
                "mac_path": "/tmp/work",
                "windows_path": "X:\\tmp\\work",
                "default": True
            },
            "data": {
                "linux_path": "/tmp/data",
                "mac_path": "/tmp/data",
                "windows_path": "X:\\tmp\\data"
            },
            "foobar": {
                "linux_path": "/tmp/foobar",
                "mac_path": "/tmp/foobar",
                "windows_path": "X:\\tmp\\foobar"
            }
        }

        # corrupt roots
        self._corrupt_roots_config_folder = os.path.join(
            roots_fixtures_folder,
            "corrupt_roots",
            "config"
        )

        # setup a temp folder for reading/writing configs
        self._config_folder = os.path.join(
            self.tank_temp,
            "test_storage_roots",
            "config"
        )
        if not os.path.exists(self._config_folder):
            os.makedirs(self._config_folder)

    def test_storage_roots_file_exists(self):
        """Test the file_exists class method."""

        self.assertTrue(StorageRoots.file_exists(self._single_root_config_folder))
        self.assertTrue(StorageRoots.file_exists(self._multiple_roots_config_folder))
        self.assertTrue(StorageRoots.file_exists(self._corrupt_roots_config_folder))
        self.assertTrue(StorageRoots.file_exists(self._empty_roots_config_folder))
        self.assertFalse(StorageRoots.file_exists(self._no_roots_config_folder))

    def test_storage_roots_from_config(self):
        """Test the from_config factory class method."""

        single_root = StorageRoots.from_config(self._single_root_config_folder)
        self.assertIsInstance(single_root, StorageRoots)

        multiple_roots = StorageRoots.from_config(self._multiple_roots_config_folder)
        self.assertIsInstance(multiple_roots, StorageRoots)

        empty_roots = StorageRoots.from_config(self._empty_roots_config_folder)
        self.assertIsInstance(empty_roots, StorageRoots)

        no_roots = StorageRoots.from_config(self._no_roots_config_folder)
        self.assertIsInstance(no_roots, StorageRoots)

        with self.assertRaises(TankError):
            StorageRoots.from_config(self._corrupt_roots_config_folder)

    def test_storage_roots_from_metadata(self):
        """Test the from_metadata factory class method."""

        single_root = StorageRoots.from_metadata(self._single_root_metadata)
        self.assertIsInstance(single_root, StorageRoots)

        multiple_roots = StorageRoots.from_metadata(self._multiple_roots_metadata)
        self.assertIsInstance(multiple_roots, StorageRoots)

        empty_roots = StorageRoots.from_metadata(self._empty_roots_metadata)
        self.assertIsInstance(empty_roots, StorageRoots)

        no_roots = StorageRoots.from_metadata(self._no_roots_metadata)
        self.assertIsInstance(no_roots, StorageRoots)

    def test_storage_roots_write(self):
        """Test the write class method."""

        config_root_folders = [
            self._single_root_config_folder,
            self._multiple_roots_config_folder,
            self._empty_roots_config_folder,
            self._no_roots_config_folder
        ]

        for config_root_folder in config_root_folders:

            storage_roots_A = StorageRoots.from_config(config_root_folder)

            out_roots_folder = os.path.join(
                self._config_folder,
                "core",
            )
            if not os.path.exists(out_roots_folder):
                os.makedirs(out_roots_folder)

            if config_root_folder == self._multiple_roots_config_folder:
                # this should raise because there is an unmapped storage (foobar)
                with self.assertRaises(TankError):
                    StorageRoots.write(self.mockgun, self._config_folder, storage_roots_A)
                continue
            else:
                # all others should without issue
                StorageRoots.write(self.mockgun, self._config_folder, storage_roots_A)

            roots_file = os.path.join(out_roots_folder, "roots.yml")
            self.assertTrue(os.path.exists(roots_file))

            storage_roots_B = StorageRoots.from_config(self._config_folder)

            self.assertEqual(storage_roots_B.roots_file, roots_file)

            self.assertEqual(
                sorted(storage_roots_A.required_roots),
                sorted(storage_roots_B.required_roots)
            )

            for root_name in storage_roots_A.required_roots:
                self.assertEqual(
                    storage_roots_A.metadata[root_name],
                    storage_roots_B.metadata[root_name],
                )

            # clean up the file written to disk
            os.remove(storage_roots_B.roots_file)

    def test_storage_roots_as_shotgun_paths(self):
        """Test the as_shotgun_paths property."""

        config_root_folders = [
            self._single_root_config_folder,
            self._multiple_roots_config_folder,
            self._empty_roots_config_folder,
            self._no_roots_config_folder
        ]

        for config_root_folder in config_root_folders:
            storage_roots = StorageRoots.from_config(config_root_folder)
            for root_name, sg_path in storage_roots.as_shotgun_paths.iteritems():
                self.assertIsInstance(sg_path, ShotgunPath)

    def test_storage_roots_default(self):
        """Test the default property."""

        single_root = StorageRoots.from_config(self._single_root_config_folder)
        self.assertEqual(single_root.default, "primary")

        multiple_roots = StorageRoots.from_config(self._multiple_roots_config_folder)
        self.assertEqual(multiple_roots.default, "work")

        empty_roots = StorageRoots.from_config(self._empty_roots_config_folder)
        self.assertEqual(empty_roots.default, None)

        no_roots = StorageRoots.from_config(self._no_roots_config_folder)
        self.assertEqual(no_roots.default, None)

    def test_storage_roots_default_path(self):
        """Test the default_path property."""

        single_root = StorageRoots.from_config(self._single_root_config_folder)
        single_root_default_path = ShotgunPath.from_shotgun_dict(
            self._single_root_metadata["primary"])
        self.assertTrue(single_root.default_path, single_root_default_path)

        multiple_roots = StorageRoots.from_config(self._multiple_roots_config_folder)
        multiple_roots_default_path = ShotgunPath.from_shotgun_dict(
            self._multiple_roots_metadata["work"])
        self.assertTrue(multiple_roots.default_path, multiple_roots_default_path)

        empty_roots = StorageRoots.from_config(self._empty_roots_config_folder)
        self.assertEqual(empty_roots.default_path, None)

        no_roots = StorageRoots.from_config(self._no_roots_config_folder)
        self.assertEqual(no_roots.default_path, None)

    def test_storage_roots_metadata(self):
        """Test the metadata property."""

        single_root = StorageRoots.from_metadata(self._single_root_metadata)
        self.assertEqual(single_root.metadata, self._single_root_metadata)

        multiple_roots = StorageRoots.from_metadata(self._multiple_roots_metadata)
        self.assertEqual(multiple_roots.metadata, self._multiple_roots_metadata)

        empty_roots = StorageRoots.from_metadata(self._empty_roots_metadata)
        self.assertEqual(empty_roots.metadata, self._empty_roots_metadata)

        no_roots = StorageRoots.from_metadata(self._no_roots_metadata)
        self.assertEqual(no_roots.metadata, self._no_roots_metadata)

    def test_storage_roots_roots_file(self):
        """Test the roots_file property."""

        relative_roots_path = os.path.join("core", "roots.yml")

        single_root = StorageRoots.from_config(self._single_root_config_folder)
        self.assertEqual(
            single_root.roots_file,
            os.path.join(self._single_root_config_folder, relative_roots_path)
        )

        multiple_roots = StorageRoots.from_config(self._multiple_roots_config_folder)
        self.assertEqual(
            multiple_roots.roots_file,
            os.path.join(self._multiple_roots_config_folder, relative_roots_path)
        )

        empty_roots = StorageRoots.from_config(self._empty_roots_config_folder)
        self.assertEqual(
            empty_roots.roots_file,
            os.path.join(self._empty_roots_config_folder, relative_roots_path)
        )

        no_roots = StorageRoots.from_config(self._no_roots_config_folder)
        self.assertEqual(
            no_roots.roots_file,
            os.path.join(self._no_roots_config_folder, relative_roots_path)
        )

    def test_storage_roots_required_roots(self):
        """Test the required_roots property."""

        single_root = StorageRoots.from_config(self._single_root_config_folder)
        single_root_required_storage_names = single_root.required_roots
        for root_name in self._single_root_metadata:
            self.assertTrue(root_name in single_root_required_storage_names)

        multiple_roots = StorageRoots.from_config(self._multiple_roots_config_folder)
        multiple_roots_required_storage_names = multiple_roots.required_roots
        for root_name in self._multiple_roots_metadata:
            self.assertTrue(root_name in multiple_roots_required_storage_names)

        empty_roots = StorageRoots.from_config(self._empty_roots_config_folder)
        self.assertEqual(empty_roots.required_roots, [])

        no_roots = StorageRoots.from_config(self._no_roots_config_folder)
        self.assertEqual(no_roots.required_roots, [])

    def test_storage_roots_get_local_storages(self):
        """Test the get_local_storages method."""

        single_root = StorageRoots.from_metadata(self._single_root_metadata)
        (single_root_lookup, unmapped_roots) = single_root.get_local_storages(self.mockgun)

        self.assertTrue("primary" in single_root_lookup)
        single_root_default = single_root_lookup["primary"]
        self.assertEqual(single_root_default["code"], "primary")
        self.assertEqual(single_root_default["type"], "LocalStorage")
        self.assertEqual(single_root_default["id"], 1)

        single_root_storage_paths = single_root.as_shotgun_paths["primary"]
        self.assertEqual(single_root_storage_paths, ShotgunPath.from_shotgun_dict(single_root_default))
        self.assertEqual(unmapped_roots, [])

        multiple_roots = StorageRoots.from_metadata(self._multiple_roots_metadata)
        (multiple_root_lookup, unmapped_roots) = multiple_roots.get_local_storages(self.mockgun)

        self.assertTrue("work" in multiple_root_lookup)
        multiple_roots_default = multiple_root_lookup["work"]
        self.assertEqual(multiple_roots_default["code"], "work")
        self.assertEqual(multiple_roots_default["type"], "LocalStorage")
        self.assertEqual(multiple_roots_default["id"], 2)

        multiple_roots_storage_paths = multiple_roots.as_shotgun_paths["work"]
        self.assertEqual(multiple_roots_storage_paths, ShotgunPath.from_shotgun_dict(multiple_roots_default))
        self.assertEqual(unmapped_roots, ["foobar"])

    def test_storage_roots_populate_defaults(self):
        """Test the populate_defaults method."""

        empty_roots_metadata = {}
        empty_roots = StorageRoots.from_metadata(empty_roots_metadata)
        empty_roots.populate_defaults()

        self.assertTrue("primary" in empty_roots.metadata)
        self.assertEqual(
            empty_roots.metadata["primary"],
            {
                "description": "Default location where project data is stored.",
                "mac_path": "/studio/projects",
                "linux_path": "/studio/projects",
                "windows_path": "\\\\network\\projects",
                "default": True,
            }
        )

        partial_roots_metadata = {
            "foobar": {
                "description": "Foobar",
                "mac_path": "/studio/projects",
                "default": True,
            }
        }
        partial_roots = StorageRoots.from_metadata(partial_roots_metadata)
        partial_roots.populate_defaults()

        self.assertEqual(
            partial_roots.metadata,
            {
                "foobar": {
                    "description": "Foobar",
                    "mac_path": "/studio/projects",
                    "linux_path": None,
                    "windows_path": None,
                    "default": True,
                }

            }
        )

    def test_update_root(self):
        """Tests the update_root method."""

        single_root = StorageRoots.from_metadata(self._single_root_metadata)
        single_root.update_root(
            "primary",
            {
                "linux_path": "/tmp/foobar",
                "mac_path": "/tmp/foobar",
                "windows_path": "X:\\tmp\\foobar",
                "shotgun_storage_id": 1,
                "default": True
            }
        )
        self.assertEqual(
            single_root.metadata,
            {
                "primary": {
                    "linux_path": "/tmp/foobar",
                    "mac_path": "/tmp/foobar",
                    "windows_path": "X:\\tmp\\foobar",
                    "shotgun_storage_id": 1,
                    "default": True
                }
            }
        )
