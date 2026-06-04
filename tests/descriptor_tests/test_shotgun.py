# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

import sgtk

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
)


class TestShotgunIODescriptor(ShotgunTestBase):
    """
    Testing the Shotgun IO descriptor
    """

    def setUp(self):
        """
        Sets up the next test's environment.
        """
        ShotgunTestBase.setUp(self)

        self.bundle_cache = os.path.join(self.project_root, "bundle_cache")

    def _create_desc(self, location):
        """Helper method"""
        return sgtk.descriptor.create_descriptor(
            self.mockgun, sgtk.descriptor.Descriptor.APP, location
        )

    def test_construction_validation(self):
        pass
    def test_construction_by_id(self):
        pass
    def test_construction_by_name(self):
        pass
    @mock.patch("sgtk.util.shotgun.download_and_unpack_attachment")
    def test_resolve_id(self, _call_rpc_mock):
        pass
    @mock.patch("sgtk.util.shotgun.download_and_unpack_attachment")
    def test_resolve_name_and_project(self, _call_rpc_mock):
        pass
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_get_latest_by_id(self, find_mock):
        pass
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_get_latest_by_name(self, find_mock):
        pass
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_get_latest_by_name_and_proj(self, find_mock):
        pass
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_find_invalid_attachment(self, find_mock):
        pass
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_missing_record(self, find_mock):
        pass
    def test_get_latest_cached_by_name(self):
        pass
    def test_get_latest_cached_by_id(self):
        pass
