# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sys

from tank_test.tank_test_base import TankTestBase, setUpModule  # noqa
from tank.util import is_windows

import sgtk


class TestHookProperties(TankTestBase):
    """
    Test basic hook parent accessors
    """

    def setUp(self):
        pass
    def test_core_hook_properties(self):
        pass
    def test_no_parent_hook_properties(self):
        pass
class TestHookGetPublishPath(TankTestBase):
    """
    Tests the hook.get_publish_path() method
    """

    def test_get_publish_path_url(self):
        pass
    def test_get_publish_path_raises(self):
        pass
    def test_get_publish_path_local_file_link(self):
        pass
