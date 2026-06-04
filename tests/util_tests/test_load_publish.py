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
import sys

import sgtk
from tank import context, errors
from tank.util import is_linux, is_macos, is_windows
from tank_test.tank_test_base import TankTestBase, setUpModule


class TestCoreHook(TankTestBase):
    """
    Tests the resolve_publish core hook
    """

    def setUp(self):
        super().setUp()
        self.setup_fixtures(name="publish_resolve")

    def test_unsupported_url(self):
        pass
    def test_supported_url(self):
        pass
    def test_supported_override(self):
        pass
class TestUnsupported(TankTestBase):
    """
    Tests unsupported publish scenarios
    """

    def setUp(self):
        super().setUp()
        self.setup_fixtures()

    def test_no_path(self):
        pass
    def test_upload(self):
        pass
    def test_unsupported_url(self):
        pass
class TestLocalFileLink(TankTestBase):
    """
    Tests path resolution of publishes to local file links
    """

    def setUp(self):
        super().setUp()
        self.setup_fixtures()

        self.storage = {
            "type": "LocalStorage",
            "id": 2,
            "code": "home",
            "mac_path": "/local",
            "windows_path": "x:\\",
            "linux_path": "/local",
        }

        self.add_to_sg_mock_db([self.storage])

    def tearDown(self):

        if "SHOTGUN_PATH_WINDOWS_HOME" in os.environ:
            del os.environ["SHOTGUN_PATH_WINDOWS_HOME"]

        if "SHOTGUN_PATH_MAC_HOME" in os.environ:
            del os.environ["SHOTGUN_PATH_MAC_HOME"]

        if "SHOTGUN_PATH_LINUX_HOME" in os.environ:
            del os.environ["SHOTGUN_PATH_LINUX_HOME"]

        super().tearDown()

    def test_basic_case(self):
        pass
    def test_env_var_warning(self):
        pass
class TestLocalFileLinkRaises(TankTestBase):
    """
    Tests path resolution of publishes to local file links

    Tests that if the current os is not recognized,
    PublishPathNotDefinedError is defined.
    """

    def setUp(self):
        super().setUp()
        self.setup_fixtures()

    def test_raises(self):
        pass
class TestLocalFileLinkEnvVarOverride(TankTestBase):
    """
    Tests path resolution of publishes to local file links

    Tests that if the current os is not defined
    in the shotgun local storage defs, we can override
    it by setting an env var.
    """

    def setUp(self):
        super().setUp()
        self.setup_fixtures()

    def tearDown(self):

        if "SHOTGUN_PATH_WINDOWS_HOME" in os.environ:
            del os.environ["SHOTGUN_PATH_WINDOWS_HOME"]

        if "SHOTGUN_PATH_MAC_HOME" in os.environ:
            del os.environ["SHOTGUN_PATH_MAC_HOME"]

        if "SHOTGUN_PATH_LINUX_HOME" in os.environ:
            del os.environ["SHOTGUN_PATH_LINUX_HOME"]

        super().tearDown()

    def test_env_var(self):
        pass
class TestUrlNoStorages(TankTestBase):
    """
    Tests urls with no storages defined
    """

    def setUp(self):
        super().setUp()
        self.setup_fixtures()

    def test_nix_path(self):
        pass
    def test_windows_drive_path(self):
        pass
    def test_windows_unc_path(self):
        pass
class TestUrlWithEnvVars(TankTestBase):
    """
    Tests url resolution with local storages and environment variables
    """

    def setUp(self):
        super().setUp()
        self.setup_fixtures()

        # set override
        os.environ["SHOTGUN_PATH_WINDOWS"] = r"\\share"
        os.environ["SHOTGUN_PATH_MAC"] = "/mac"
        os.environ["SHOTGUN_PATH_LINUX"] = "/linux"

        os.environ["SHOTGUN_PATH_WINDOWS_2"] = "X:\\"
        os.environ["SHOTGUN_PATH_MAC_2"] = "/altmac"
        os.environ["SHOTGUN_PATH_LINUX_2"] = "/altlinux"

    def tearDown(self):

        del os.environ["SHOTGUN_PATH_WINDOWS"]
        del os.environ["SHOTGUN_PATH_MAC"]
        del os.environ["SHOTGUN_PATH_LINUX"]
        del os.environ["SHOTGUN_PATH_WINDOWS_2"]
        del os.environ["SHOTGUN_PATH_MAC_2"]
        del os.environ["SHOTGUN_PATH_LINUX_2"]

        super().tearDown()

    def test_no_storages(self):
        pass
    def test_windows_unc(self):
        pass
    def test_windows_drive(self):
        pass
    def test_nix(self):
        pass
class TestUrlWithStorages(TankTestBase):
    """
    Tests url resolution with local storages
    """

    def setUp(self):
        super().setUp()

        self.setup_fixtures()

        self.storage = {
            "type": "LocalStorage",
            "id": 1,
            "code": "storage_1",
            "mac_path": "/storage1_mac",
            "windows_path": "x:\\storage1_win\\",
            "linux_path": "/storage1_linux/",
        }

        self.storage_2 = {
            "type": "LocalStorage",
            "id": 2,
            "code": "storage_2",
            "mac_path": "/storage2_mac/",
            "windows_path": r"\\storage2_win",
            "linux_path": "/storage2_linux",
        }

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.storage, self.storage_2])

    def test_no_storages(self):
        pass
    def test_local_storage_windows_unc(self):
        pass
    def test_local_storage_windows_drive(self):
        pass
    def test_local_storage_nix(self):
        pass
class TestUrlWithStoragesAndOverrides(TankTestBase):
    """
    Tests file:// url resolution with local storages and environment overrides
    """

    def setUp(self):
        super().setUp()

        self.setup_fixtures()

        self.storage = {
            "type": "LocalStorage",
            "id": 1,
            "code": "storage_1",
            "windows_path": r"\\storage_win",
        }

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.storage])

    def test_augument_local_storage(self):
        pass
class TestUrlWithStoragesAndOverrides2(TankTestBase):
    """
    Tests file:// url resolution with local storages and
    additive environment overrides.
    """

    def setUp(self):
        super().setUp()

        self.setup_fixtures()

        self.storage = {
            "type": "LocalStorage",
            "id": 1,
            "code": "storage_1",
            "mac_path": "/storage_mac",
            "windows_path": "x:\\storage_win\\",
            "linux_path": "/storage_linux/",
        }

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.storage])

        os.environ["SHOTGUN_PATH_MAC_STORAGE_1"] = "/storage_mac_alt"
        os.environ["SHOTGUN_PATH_LINUX_STORAGE_1"] = "/storage_linux_alt"
        os.environ["SHOTGUN_PATH_WINDOWS_STORAGE_1"] = "x:\\storage_win_alt"

    def tearDown(self):
        del os.environ["SHOTGUN_PATH_MAC_STORAGE_1"]
        del os.environ["SHOTGUN_PATH_LINUX_STORAGE_1"]
        del os.environ["SHOTGUN_PATH_WINDOWS_STORAGE_1"]

        super().tearDown()

    def test_augument_local_storage(self):
        pass
