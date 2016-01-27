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
    Returns the official sgtk root logger
    """
    if name is None:
        return sgtk_root_logger
    else:
        return logging.getLogger("sgtk.%s" % name)

