# Copyright (c) 2020 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Unit tests for interactive authentication.
"""

from unittest import TestCase
import logging

from tank_vendor import shotgun_authentication


class TestBackwardsCompatibility(TestCase):
    """
    Ensure the tank_vendor.shotgun_authentication shim works as expected.
    """

    def test_attributes(self):
        pass
    def test_get_logger(self):
        pass
