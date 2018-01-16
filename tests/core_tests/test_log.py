# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import copy

import sgtk

from tank_test.tank_test_base import setUpModule # noqa
from tank_test.tank_test_base import ShotgunTestBase


class TestLogManager(ShotgunTestBase):
    """Tests the LogManager interface."""
    def test_global_debug_environment(self):
        """
        Ensures that the debug logging environment variable is set/unset when
        the global debug logging property is toggled.
        """
        manager = sgtk.log.LogManager()
        original_env = copy.copy(os.environ)
        original_debug = manager.global_debug
        debug_name = sgtk.constants.DEBUG_LOGGING_ENV_VAR

        try:
            if debug_name in os.environ:
                del os.environ[debug_name]

            manager.global_debug = True
            self.assertIn(debug_name, os.environ)

            manager.global_debug = False
            self.assertNotIn(debug_name, os.environ)
        finally:
            manager.global_debug = original_debug
            os.environ = original_env
