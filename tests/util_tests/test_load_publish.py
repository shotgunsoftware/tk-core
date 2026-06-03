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
        pass
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
        pass
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
        pass
    def tearDown(self):
        pass
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
        pass
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
        pass
    def tearDown(self):
        pass
    def test_env_var(self):
        pass
class TestUrlNoStorages(TankTestBase):
    """
    Tests urls with no storages defined
    """

    def setUp(self):
        pass
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
        pass
    def tearDown(self):
        pass
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
        pass
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
        pass
    def test_augument_local_storage(self):
        pass
class TestUrlWithStoragesAndOverrides2(TankTestBase):
    """
    Tests file:// url resolution with local storages and
    additive environment overrides.
    """

    def setUp(self):
        pass
    def tearDown(self):
        pass
    def test_augument_local_storage(self):
        pass
