# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Logging configuration for this module.
"""

import logging

# Initialize the logger.
_logger = logging.getLogger("sg_auth")
_logger.setLevel(logging.WARNING)


def get_logger():
    """
    Returns the root level logger for this module.
    """
    global _logger
    return _logger
