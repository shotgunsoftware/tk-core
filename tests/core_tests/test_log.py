# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import logging
from sgtk import LogManager

from unittest2 import TestCase


class LoggingTests(TestCase):
    """
    Tests around the logging.
    """

    def test_attach_detach(self):
        """
        Make sure that the handler gets attached only once.
        """
        outside_logger = logging.getLogger("outside_logger")

        # Make sure we're attaching ourselves
        self.assertEqual(len(outside_logger.handlers), 0)
        LogManager().attach_external_logger(outside_logger)
        self.assertEqual(len(outside_logger.handlers), 1)

        # Make sure we're still attached once.
        LogManager().attach_external_logger(outside_logger)
        self.assertEqual(len(outside_logger.handlers), 1)

        # Make sure detaching works.
        LogManager().detach_external_logger(outside_logger)
        self.assertEqual(len(outside_logger.handlers), 0)

        # Make sure detaching another time doesn't cause an error.
        LogManager().detach_external_logger(outside_logger)

    class CountingFilter(logging.Filterer):
        def __init__(self):
            super(LoggingTests.CountingFilter, self).__init__()
            self.count = 0

        def filter(self, record):
            # If the logging is coming from some else, we don't care about it.
            # we only want to count the number of messages that have been
            # rerouted.
            if record.name.startswith("sgtk.ext.outside_logger"):
                self.count += 1

    def test_rerouting(self):
        """
        Makes sure messages are rerouted properly based on the log level.
        """
        outside_logger = logging.getLogger("outside_logger")
        sub_logger = logging.getLogger("outside_logger.sub_logger")
        LogManager().attach_external_logger(outside_logger)

        # Attach a filter that will count how many logs are sent to the
        # Toolkit log's handlers from sgtk.ext.outside_logger
        counting_filter = self.CountingFilter()
        LogManager().base_file_handler.addFilter(counting_filter)

        original_global_debug = LogManager().global_debug

        try:
            # First disable the global logging flag, we should log everything
            # except DEBUG messages.
            LogManager().global_debug = False

            outside_logger.error("Error!")
            self.assertEqual(counting_filter.count, 1)

            outside_logger.warning("Warning!")
            self.assertEqual(counting_filter.count, 2)

            outside_logger.info("Info!")
            self.assertEqual(counting_filter.count, 3)

            outside_logger.debug("Debug!")
            self.assertEqual(counting_filter.count, 3)

            # Turn debug_logging on, we should now be able to log those messages
            # as well.
            LogManager().global_debug = True

            outside_logger.debug("Debug!")
            self.assertEqual(counting_filter.count, 4)

            # Turn it back off and we'll now log with a sub logger. Nothing should
            # change in the behaviour.
            LogManager().global_debug = False

            sub_logger.error("Error!")
            self.assertEqual(counting_filter.count, 5)

            sub_logger.warning("Warning!")
            self.assertEqual(counting_filter.count, 6)

            sub_logger.info("Info!")
            self.assertEqual(counting_filter.count, 7)

            sub_logger.debug("Debug!")
            self.assertEqual(counting_filter.count, 7)

            # Turn back debug_logging to one and it should log once again.
            LogManager().global_debug = True

            sub_logger.debug("Debug!")
            self.assertEqual(counting_filter.count, 8)
        finally:
            # Reset to whatever the tests were set to originally.
            LogManager().global_debug = original_global_debug
