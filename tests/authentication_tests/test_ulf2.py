# Copyright (c) 2023 Autodesk.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Unit tests for Unified Login Flow 2 authentication.
"""

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    ShotgunTestBase,
)

from tank.authentication import (
    unified_login_flow2,
)


class ULF2Tests(ShotgunTestBase):
    def test_process_parameters(self):
        with self.assertRaises(AssertionError):
            unified_login_flow2.process(
                "https://test.shotgunstudio.com",
                product=None,
            )

        with self.assertRaises(AssertionError):
            unified_login_flow2.process(
                "https://test.shotgunstudio.com",
                product="my_app",
                browser_open_callback=None,
            )

        with self.assertRaises(AssertionError):
            unified_login_flow2.process(
                "https://test.shotgunstudio.com",
                product="my_app",
                browser_open_callback="Test",
            )

        with self.assertRaises(AssertionError):
            unified_login_flow2.process(
                "https://test.shotgunstudio.com",
                product="my_app",
                browser_open_callback=lambda: True,
                keep_waiting_callback=None,
            )
