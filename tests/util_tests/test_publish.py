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

import tank
from tank import context, errors
from tank.util import is_windows
from tank_test.tank_test_base import (
    mock,
    TankTestBase,
    setUpModule,
    only_run_on_windows,
    only_run_on_nix,
)


class TestShotgunRegisterPublish(TankTestBase):
    def setUp(self):
        pass
    def test_local_storage_disabled(self):
        pass
    def test_sequence_abstracted_path(self):
        pass
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.create")
    def test_url_paths(self, create_mock):
        pass
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.create")
    def test_url_paths_host(self, create_mock):
        pass
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.create")
    def test_local_storage_publish(self, create_mock):
        pass
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.create")
    def test_freeform_publish(self, create_mock):
        pass
    def test_no_thumbnail_skips_upload(self):
        pass
    def test_publish_errors(self):
        pass
class TestMultiRoot(TankTestBase):
    def setUp(self):
        pass
    def test_storage_misdirection(self):
        pass
class TestCalcPathCache(TankTestBase):
    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_case_difference(self, get_local_storage_roots):
        pass
    @only_run_on_windows
    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_path_normalization_win_drive_letter(self, get_local_storage_roots):
        pass
    @only_run_on_windows
    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_path_normalization_win_unc(self, get_local_storage_roots):
        pass
    @only_run_on_nix
    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_path_normalization_nix(self, get_local_storage_roots):
        pass
    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_project_names_only_current_project(self, get_local_storage_roots):
        pass
    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_project_names_multiple(self, get_local_storage_roots):
        pass
class TestCalcPathCacheProjectWithSlash(TankTestBase):
    def setUp(self):
        pass
    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_multi_project_root(self, get_local_storage_roots):
        pass
