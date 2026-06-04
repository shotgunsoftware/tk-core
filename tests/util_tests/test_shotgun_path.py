# Copyright (c) 2013 Shotgun Software Inc.
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

from tank.util import ShotgunPath, is_linux, is_macos, is_windows


class TestShotgunPath(ShotgunTestBase):
    """
    tests the ShotgunPath class
    """

    def setUp(self):
        super().setUp()

    def test_construction(self):
        pass
    def test_property_access(self):
        pass
    def test_sanitize(self):
        pass
    def test_equality(self):
        pass
    def test_shotgun(self):
        pass
    def test_join(self):
        pass
    def test_get_shotgun_storage_key(self):
        pass
    def test_truthiness(self):
        pass
    def test_normalize(self):
        pass
    def test_current_platform_file(self):
        pass
    def test_hashing(self):
        pass
    def test_as_descriptor_uri(self):
        pass
