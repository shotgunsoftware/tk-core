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

from tank_vendor.shotgun_base import get_sgtk_logger


def get_logger(name=None):
    """
    Return the sgtk authentication logger.

    If the name parameter is left as None, the sgtk authentication logger
    itself is returned.

    If the name parameter is set, a child logger will be created using
    the name parameter.

    For example:

        log = get_logger() # returns the sgtk.auth logger
        log = get_sgtk_logger("foo") # returns the sgtk.auth.foo logger

    :param name: Child logger channel to return. For nested levels, use
        periods.
    :returns: Python logger
    """
    if name:
        return get_sgtk_logger("auth." + name)
    else:
        return get_sgtk_logger("auth")
