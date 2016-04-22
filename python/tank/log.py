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
import logging.handlers
import os

from .paths import get_logs_root

sgtk_root_logger = logging.getLogger("sgtk")
sgtk_root_logger.propagate = False
# the basic logger object has its message throughput
# level set to DEBUG. Individual handlers attaching
# to this logger should then individually adjust
# their preferred display level.
sgtk_root_logger.setLevel(logging.DEBUG)

# a global and standard rotating log file handler
# for writing generic toolkit logs to disk
std_file_handler = None

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

def initialize_base_file_logger(log_name):
    """
    Create a standard handler and attach it to the stgk base logger.
    This will write a file to disk in a standard location and will capture
    all log messages pass through the stgk log hierarchy.

    In order to avoid writing out the same log information
    in multiple files, this method ensures that only one
    base file logger can exist at one time. If this method
    is called multiple times with different log names, only
    the last one will be active.

    :param log_name: Name of logger to create. This will form the
                     filename of the log file.
    """
    # avoid cyclic imports
    from .util.filesystem import ensure_folder_exists
    from .util.filesystem import create_valid_filename

    global std_file_handler

    if std_file_handler:
        # there is already a log handler.
        # terminate previous one
        get_shotgun_base_logger().removeHandler(std_file_handler)
        std_file_handler = None

    # set up logging root folder
    log_folder = get_logs_root()
    ensure_folder_exists(log_folder)

    # generate log path
    log_file = os.path.join(
        log_folder,
        "%s.log" % create_valid_filename(log_name)
    )

    std_file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=1024*1024,
        backupCount=5)
    formatter = logging.Formatter(
        "%(asctime)s [%(process)-5d %(levelname)-7s] %(name)s - %(message)s"
    )
    std_file_handler.setFormatter(formatter)
    get_sgtk_logger().addHandler(std_file_handler)

    # log the fact that we set up the log file :)
    log = get_shotgun_base_logger()
    log.debug("Writing to log standard log file %s" % log_file)