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
        """
        Ensure all attributes are present.
        """
        attrs = [
            "ShotgunAuthenticationError",
            "AuthenticationError",
            "IncompleteCredentials",
            "AuthenticationCancelled",
            "ShotgunAuthenticator",
            "DefaultsManager",
            "deserialize_user",
            "serialize_user",
            "get_logger",
        ]

        for attr in attrs:
            assert hasattr(shotgun_authentication, attr)

    def test_get_logger(self):
        """
        Ensure the logger returned is the one from the authentication module so logged
        message get through it.
        """
        assert isinstance(shotgun_authentication.get_logger(), logging.Logger)
        assert shotgun_authentication.get_logger().name == "sgtk.core.authentication"
