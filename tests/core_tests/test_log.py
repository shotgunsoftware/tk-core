# -*- coding: utf-8 -*-
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
from mock import patch

from tank_test.tank_test_base import setUpModule  # noqa
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

    def test_log_file_property(self):
        """
        Tests the LogManager 'log_file' property
        """
        manager = sgtk.log.LogManager()
        self.assertTrue(hasattr(manager, "log_file"))
        self.assertIsNotNone(manager.log_file)

    def test_writing_unicode_to_log(self):
        """
        Ensure we can write unicode to a log file on all platforms.
        """
        manager = sgtk.log.LogManager()
        unicode_str = "司狼 神威"

        # When a logger's emit method fails, the handleError method is called.
        with patch.object(
            manager.base_file_handler, "handleError"
        ) as handle_error_mock:
            # This used to not log.
            manager.root_logger.warning(unicode_str)
            # Flush the data to disk to make sure the data is emitted.
            manager.base_file_handler.flush()

        assert handle_error_mock.call_count == 0
