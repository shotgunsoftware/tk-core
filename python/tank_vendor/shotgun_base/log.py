# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import logging

sgtk_root_logger = logging.getLogger("sgtk")
sgtk_root_logger.propagate = False

def get_sgtk_logger(name=None):
    """
    Returns a official sgtk root logger.

    If the name parameter is left as None, the root
    logger itself is returned. This logger is not meant
    to be used to for actual logging, but instead you
    attach your log handlers to this log. By attaching
    a log handler at this level, you will catch all
    sgtk related messages.

    If you are logging inside of your code, use
    the name parameter to generate a child logger
    which will be parented under the main sgtk
    logger. For example::

        log = get_sgtk_logger("maya_plugin")
        log = get_sgtk_logger("maya_plugin.bootstrap")

    :param name: Child logger channel to return.
                 For nested levels, use periods.
    :returns: Python logger
    """
    if name is None:
        return sgtk_root_logger
    else:
        return logging.getLogger("sgtk.%s" % name)

def get_shotgun_base_logger():
    """
    Returns a logger to be used inside the shotun_base module

    :return: Python logger
    """
    return get_sgtk_logger("base")
