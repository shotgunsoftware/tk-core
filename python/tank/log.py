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
import time
from functools import wraps
from . import constants

log = logging.getLogger(__name__)

class LogManager(object):
    """
    Main interface for logging in Toolkit.

    This class contains a series of methods to help standardize log output
    and access. Since Toolkit uses the standard python logging interface,
    you can manually configure and associate your logging if you like.
    """
    # a global and standard rotating log file handler
    # for writing generic toolkit logs to disk
    _std_file_handler = None

    @classmethod
    def initialize_std_handler(cls, handler=logging.StreamHandler()):
        """
        Convenience method that initializes a standard logger
        and attaches it to the toolkit logging root.

        Calling this without parameters will generate a standard
        stream based logging handler that logs to stderr::

            # start logging to stderr
            import sgtk.LogManager
            LogManager.initialize_std_handler()

        If you want to log to a file instead, create a log handler
        and pass that to the method::

            handler = logging.FileHandler("/tmp/toolkit.log)
            LogManager.initialize_std_handler(handler)

        If you want to only show warnings::

            # start logging to stderr
            import sgtk.LogManager
            handler = LogManager.initialize_std_handler()
            handler.setLevel(logging.WARNING)

        The log handler will be configured to output its messages
        in a standard fashion.

        :param handler: Logging handler to connect with the toolkit logger.
                        If not passed, a standard stream logger will be created.
        :return: The configured log handler.
        """
        # example:
        # [DEBUG tank.log] message message
        formatter = logging.Formatter(
            "[%(levelname)s %(name)s] %(message)s"
        )

        handler.setFormatter(formatter)
        sgtk_root_logger.addHandler(handler)

        return handler


    @classmethod
    def get_root_logger(cls):
        """
        Returns the root logger for Toolkit.

        If you want to add your own logger underneath the toolkit
        logger, you can use this method to easily do so::

            log = get_root_logger().getChild("my_logger")

        This will create a ``my_logger`` under the root logger and
        log information from this will appear in all standard toolkit
        logs.

        .. note:: If you want to add a custom logging handler to the root logger,
                  we recommend using the :meth:`LogManager.initialize_std_handler`
                  convenience method.

        .. warning:: The root logger logs down to a debug resolution by default.
                     Do not change the output level of logger as this will have
                     a global effect. If you are connecting a logging handler
                     and want to limit the stream of messages that are being
                     emitted, instead adjust the logging level of the handler.

        :return: log object
        """
        return logging.getLogger(constants.ROOT_LOGGER_NAME)

    @classmethod
    def initialize_base_file_logger(cls, log_name):
        """
        Create a file writer and attach it to the stgk base logger.
        This will write a rotating log file to disk in a standard
        location and will capture all log messages passed through
        the log hierarchy.

        .. info:: Files will be written into the logging location
                  defined by :meth:`LocalFileStorageManager.get_global_root`.

        If you launch toolkit via the :class:`sgtk.bootstrap.ToolkitManager`,
        this logger will be automatically set up and logging information
        that can be used for diagnostics or troubleshooting.

        If you are manually launching toolkit, we recommend that you call
        this method to initialize logging to file. Calling it multiple times
        will not result in the information being written to multiple different
        files - only one file logger can exist per Toolkit session.

        :param log_name: Name of logger to create. This will form the
                         filename of the log file.
        """
        # avoid cyclic references
        from .util import LocalFileStorageManager
        from .util import filesystem

        if cls._std_file_handler:
            # there is already a log handler.
            # terminate previous one
            sgtk_root_logger.removeHandler(cls._std_file_handler)
            cls._std_file_handler = None

        # set up logging root folder
        log_folder = LocalFileStorageManager.get_global_root(LocalFileStorageManager.LOGGING)
        filesystem.ensure_folder_exists(log_folder)

        # generate log path
        log_file = os.path.join(
            log_folder,
            "%s.log" % filesystem.create_valid_filename(log_name)
        )

        cls._std_file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=4096*1024,
            backupCount=5
        )

        # example:
        # 2016-04-25 08:56:12,413 [44862 DEBUG tank.log] message message
        formatter = logging.Formatter(
            "%(asctime)s [%(process)d %(levelname)s %(name)s] %(message)s"
        )

        cls._std_file_handler.setFormatter(formatter)
        sgtk_root_logger.addHandler(cls._std_file_handler)

        # log the fact that we set up the log file :)
        log.debug("Writing to log standard log file %s" % log_file)


def log_timing(name=None):
    """
    Decorator that times and logs the execution of a method.

    Sometimes it is useful to log runtime statistics about
    how long time a certain method takes to execute. In the
    case of Toolkit, it is particularly helpful when debugging
    issues to do with I/O or cloud connectivity.

    If you have a method that for example connects to Shotgun to
    retrieve data, you can decorate it::

        @log_timing("Publishing to Shotgun")
        def my_shotgun_publish_method():
            '''
            Publishes lots of files to Shotgun
            '''
            # shotgun code here

    In the debug logs, timings will be written to the
    ``tank.stopwatch`` logger::

        [DEBUG tank.stopwatch] Publishing to Shotgun: 0.633s

    """
    def _my_decorator(func):
        def _decorator(*args, **kwargs):
            time_before = time.time()
            try:
                response = func(*args, **kwargs)
            finally:
                time_spent = time.time() - time_before
                # log to special timing logger
                timing_logger = logging.getLogger(constants.PROFILING_LOG_CHANNEL)
                timing_logger.debug("%s: %fs" % (name, time_spent))
            return response
        return wraps(func)(_decorator)
    return _my_decorator



# initialize toolkit logging
#
# retrieve top most logger in the sgtk hierarchy
sgtk_root_logger = logging.getLogger(constants.ROOT_LOGGER_NAME)
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
# and add it to the logger
sgtk_root_logger.addHandler(NullHandler())

