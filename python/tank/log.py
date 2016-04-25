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
from .paths import PathManager
from .util import filesystem

class LogManager(object):
    """
    Interface for logging in Toolkit
    """
    # the name of the root point of all toolkit
    # logging
    ROOT_LOGGER_NAME = "tank"

    # a global and standard rotating log file handler
    # for writing generic toolkit logs to disk
    _std_file_handler = None

    @classmethod
    def get_root_logger(cls):
        """
        Returns the root logger for sgtk.

        This method is typically used for two different purposes:

        - If you want to add your own logger underneath the toolkit
          logger, you can use this method to easily do so::

            log = get_root_logger().getChild("my_logger")

          This will create a ``my_logger`` under the root logger and
          log information from this will appear in all standard toolkit
          logs.

        - If you want to control how log information is being output. This
          is done by adding a handler to the root logger. The handler can send
          the information to stdout, write it to a file etc. Please note that if
          you want your log handler to output less information, for example only
          warning and errors, do not adjust the log level on the logger itself.
          Instead, adjust the log level on the log handler you are creating. This
          will ensure that the right amount of information is written to log files.

        :return: log object
        """
        return logging.getLogger(cls.ROOT_LOGGER_NAME)

    @classmethod
    def initialize_base_file_logger(cls, log_name):
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
        if cls.std_file_handler:
            # there is already a log handler.
            # terminate previous one
            sgtk_root_logger.removeHandler(cls.std_file_handler)
            cls.std_file_handler = None

        # set up logging root folder
        log_folder = PathManager.get_global_root(PathManager.LOGGING)
        filesystem.ensure_folder_exists(log_folder)

        # generate log path
        log_file = os.path.join(
            log_folder,
            "%s.log" % filesystem.create_valid_filename(log_name)
        )

        std_file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=1024*1024,
            backupCount=5
        )

        # example:
        # 2016-04-25 08:56:12,413 [44862 DEBUG tank.log] message message
        formatter = logging.Formatter(
            "%(asctime)s [%(process)d %(levelname)s %(name)s] %(message)s"
        )

        std_file_handler.setFormatter(formatter)
        sgtk_root_logger.addHandler(std_file_handler)

        # log the fact that we set up the log file :)
        log = logging.getLogger(__name__)
        log.debug("Writing to log standard log file %s" % log_file)



# initialize toolkit logging
#
# retrieve top most logger in the sgtk hierarchy
sgtk_root_logger = logging.getLogger(LogManager.ROOT_LOGGER_NAME)
# 'cap it' so that log messages don't propagate
# further upwards in the hierarchy. This is to avoid
# log message spilling over into other loggers; if you
# want to receive toolkit log messages, you have to
# explicitly attach a log handler to the sgtk top level
# logger (or any of its child loggers).
sgtk_root_logger.propagate = False
# The top level logger object has its message throughput
# level set to DEBUG. Individual handlers attaching
# to this logger should then individually adjust
# their preferred display level.
sgtk_root_logger.setLevel(logging.DEBUG)
#
# create a 'nop' log handler to be attached.
# this is to avoid warnings being reported that
# logging is missing.
#
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
#
sgtk_root_logger.addHandler(NullHandler())
