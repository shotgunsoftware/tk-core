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
Unit tests tank validate.
"""

import logging

from tank_test.tank_test_base import TankTestBase, setUpModule  # noqa

from tank_test.mock_appstore import patch_app_store


class TestSimpleValidate(TankTestBase):
    """
    Makes sure environment code works with the app store mocker.
    """

    def setUp(self):
        pass
    def test_simple_validate(self):
        pass
