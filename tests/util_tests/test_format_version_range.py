# Copyright (c) 2024 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import ShotgunTestBase
from tank.util.version import format_version_range


class TestFormatVersionRange(ShotgunTestBase):
    def setUp(self):
        super().setUp()

    def test_open_ended_range(self):
        self.assertEqual(format_version_range("1.2.3"), ">=1.2.3")

    def test_bounded_range(self):
        self.assertEqual(format_version_range("1.2.3", "2.0.0"), ">=1.2.3, <2.0.0")
