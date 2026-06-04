# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Unit tests tank setup_project.
"""

import os
import logging

import tank
from tank.util import is_linux, is_macos, is_windows
from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    TankTestBase,
)

from tank_test.mock_appstore import patch_app_store


class TestSetupProject(TankTestBase):
    """
    Tests related to a toolkit project setup
    """

    def setUp(self):
        """
        Prepare unit test.
        """
        TankTestBase.setUp(
            self,
            # Use a custom primary root name
            parameters={"primary_root_name": "setup_project_root"},
        )
        self.setup_fixtures("app_store_tests")

        patcher = patch_app_store()
        self._mock_store = patcher.start()
        self.addCleanup(patcher.stop)

        # Make sure we have a version in the app store for all bundles.
        self._mock_store.add_engine("tk-engine", "v1.0.0")
        self._mock_store.add_engine("tk-test", "v1.0.0")
        self._mock_store.add_application("tk-multi-app", "v1.0.0")
        self._mock_store.add_application("tk-multi-nodep", "v1.0.0")
        self._mock_store.add_framework("tk-framework-test", "v1.0.0")
        self._mock_store.add_framework("tk-framework-2nd-level-dep", "v1.0.0")

        # the std fixtures do not have a full core installation so ensure
        # that we mock one that localize can pick up
        self._fake_core_install = os.path.join(self.tank_temp, "fake_core_install")
        if not os.path.exists(self._fake_core_install):
            os.makedirs(os.path.join(self._fake_core_install, "install"))
            os.makedirs(os.path.join(self._fake_core_install, "install", "core"))
            os.makedirs(
                os.path.join(self._fake_core_install, "install", "core", "fake_core")
            )
            os.makedirs(os.path.join(self._fake_core_install, "config"))
            cfg_core = os.path.join(self._fake_core_install, "config", "core")
            os.makedirs(cfg_core)
            self.create_file(
                os.path.join(cfg_core, "shotgun.yml"),
                "{host: http://unit_test_mock_sg}",
            )
            self.create_file(os.path.join(cfg_core, "interpreter_Darwin.cfg"), "")
            self.create_file(os.path.join(cfg_core, "interpreter_Linux.cfg"), "")
            self.create_file(os.path.join(cfg_core, "interpreter_Windows.cfg"), "")

    @mock.patch("tank.pipelineconfig_utils.resolve_all_os_paths_to_core")
    def test_setup_centralized_project(self, mocked=None):
        pass
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.upload")
    @mock.patch("tank.pipelineconfig_utils.resolve_all_os_paths_to_core")
    def test_setup_distributed_project(
        self, resolve_all_os_paths_to_core_mock, upload_mock
    ):
        pass
    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_install_location")
    @mock.patch("tank.pipelineconfig_utils.resolve_all_os_paths_to_core")
    def test_setup_project_with_external_core(
        self, resolve_all_os_paths_to_core_mock, get_install_location_mock
    ):
        pass
