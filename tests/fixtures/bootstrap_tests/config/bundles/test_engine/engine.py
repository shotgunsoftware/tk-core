# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
A simple engine to support unit tests.
"""

from tank.platform import Engine
import sys


class TestEngine(Engine):
    """
    Engine stub for unit testing.
    """

    def init_engine(self):
        """
        Called when engine is initialized.
        """
        self._context_change_enabled = False

    @property
    def context_change_allowed(self):
        """
        :returns: True if context change is supported, False otherwise.
        """
        return self._context_change_enabled

    def enable_context_change(self):
        """
        Enables context change.
        """
        self._context_change_enabled = True

    ##########################################################################################
    # logging interfaces

    def log_debug(self, msg):
        """
        Prints debug message to the console.

        :param msg: Message to print.
        """
        if self.get_setting("debug_logging", False):
            sys.stdout.write("DEBUG: %s\n" % msg)

    def log_info(self, msg):
        """
        Prints info message to the console.

        :param msg: Message to print.
        """
        sys.stdout.write("%s\n" % msg)

    def log_warning(self, msg):
        """
        Prints warning message to the console.

        :param msg: Message to print.
        """
        sys.stdout.write("WARNING: %s\n" % msg)

    def log_error(self, msg):
        """
        Prints error message to the console.

        :param msg: Message to print.
        """
        sys.stdout.write("ERROR: %s\n" % msg)
