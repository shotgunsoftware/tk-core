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

# the logger for logging messages from this file :)
log = logging.getLogger(__name__)

class LogManager(object):
    """
    Main interface for logging in Toolkit.

    This class contains a series of methods to help standardize log output
    and access. Since Toolkit uses the standard python logging interface,
    you can manually configure and associate your logging if you like.

    .. note:: This is a singleton class, so every time you instantiate it,
              the same object is returned.
    """

    # keeps track of the single instance of the class
    __instance = None

    def __new__(cls, *args, **kwargs):
        """
        Ensures only one instance of the log manager exists.
        """
        # create the instance if it hasn't been created already
        if not cls.__instance:
            # remember the instance so that no more are created
            instance = super(LogManager, cls).__new__(
                cls,
                *args,
                **kwargs
            )

            # a global and standard rotating log file handler
            # for writing generic toolkit logs to disk
            instance._std_file_handler = None
            instance._std_file_handler_log_name = None

            # the root logger, created at code init
            instance._root_logger = logging.getLogger(constants.ROOT_LOGGER_NAME)

            # check the TK_DEBUG flag at startup
            if constants.DEBUG_LOGGING_ENV_VAR in os.environ:
                instance.global_debug = True

            cls.__instance = instance


        return cls.__instance

    def _set_global_debug(self, state):
        """
        Sets the state of the global debug in toolkit.
        """
        if state:
            self.root_logger.setLevel(logging.DEBUG)
            log.debug(
                "Debug logging was enabled. To permanently enable it, "
                "set the %s environment variable." % constants.DEBUG_LOGGING_ENV_VAR
            )
        else:
            log.debug("Disabling debug logging.")
            self.root_logger.setLevel(logging.INFO)

    def _get_global_debug(self):
        """
        Returns whether the toolkit main logger has got
        debug log turned on or not. Controlling this property
        has a global impact and affects all services attached
        to the logger.

        .. note:: Debug logging is off by default.
                  If you want to permanently enable debug logging,
                  set the environment variable ``TK_DEBUG``.
        """
        return self.root_logger.isEnabledFor(logging.DEBUG)

    global_debug = property(_get_global_debug, _set_global_debug)

    def initialize_custom_handler(self, handler=logging.StreamHandler()):
        """
        Convenience method that initializes a log handler
        and attaches it to the toolkit logging root.

        .. note:: If you want to display log messages inside a DCC,
                  implement :meth:`~sgtk.platform.Engine._emit_log_message`.


        Calling this without parameters will generate a standard
        stream based logging handler that logs to stderr::

            # start logging to stderr
            import sgtk.LogManager
            LogManager().initialize_custom_handler()

        If you want to log to a file instead, create a log handler
        and pass that to the method::

            handler = logging.FileHandler("/tmp/toolkit.log)
            LogManager().initialize_custom_handler(handler)

        If you want to only show warnings::

            # start logging to stderr
            import sgtk.LogManager
            handler = LogManager().initialize_custom_handler()
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
        self._root_logger.addHandler(handler)

        return handler

    @staticmethod
    def get_child_logger(logger, log_name):
        """
        Utility method that returns a logger parented under the given logger.

        The two following lines are equivalent::

            sgtk.LogManager().root_logger.getChild("foo").getChild("bar")
            sgtk.LogManager.get_child_logger(sgtk.LogManager().root_logger, "foo.bar")

        .. note:: This method is mainly included due to the ``getChild()``
                  method not existing in Python 2.6.

        :param logger: Logger object to use as base
        :param log_name: child logger string with each level separated by periods.
        :return: std python logging object
        """
        full_log_path = "%s.%s" % (logger.name, log_name)
        return logging.getLogger(full_log_path)

    def get_root_child_logger(self, log_name):
        """
        Convenience method that returns a child logger parented under the root logger.

        The two following lines are equivalent::

            sgtk.LogManager().get_sgtk_child_logger("foo.bar")
            sgtk.LogManager.get_child_logger(sgtk.LogManager().root_logger, "foo.bar")

        .. note:: This method is mainly included due to the ``getChild()``
                  method not existing in Python 2.6.

        :param log_name: child logger string with each level separated by periods.
        :return: std python logging object
        """
        return self.get_child_logger(self.root_logger, log_name)

    @property
    def log_folder(self):
        """
        The folder where log files generated by :meth:`initialize_base_file_handler` are stored.
        """
        # avoid cyclic references
        from .util import LocalFileStorageManager
        return LocalFileStorageManager.get_global_root(LocalFileStorageManager.LOGGING)

    @property
    def root_logger(self):
        """
        Returns the root logger for Toolkit.

        If you want to add your own logger underneath the toolkit
        logger, you can use this method to easily do so::

            root_logger = sgtk.LogManager().root_logger
            child_logger sgtk.LogManager.get_child_logger(root_logger, "my_logger")

        This will create a ``my_logger`` under the root logger and
        log information from this will appear in all standard toolkit
        logs.

        .. note:: If you want to add a custom logging handler to the root logger,
                  we recommend using the :meth:`LogManager().initialize_custom_handler`
                  convenience method.

        .. warning:: The root logger logs down to a debug resolution by default.
                     Do not change the output level of logger as this will have
                     a global effect. If you are connecting a logging handler
                     and want to limit the stream of messages that are being
                     emitted, instead adjust the logging level of the handler.

        :return: log object
        """
        return self._root_logger

    @property
    def base_file_handler(self):
        """
        The base file handler that is used to write log files to disk
        in a default location, or None if not defined.
        """
        return self._std_file_handler

    def initialize_base_file_handler(self, log_name):
        """
        Create a file handler and attach it to the stgk base logger.
        This will write a rotating log file to disk in a standard
        location and will capture all log messages passed through
        the log hierarchy.

        .. note:: Files will be written into the logging location
                  defined by :meth:`log_folder`.

        When you start an engine via the :meth:`sgtk.platform.start_engine` method,
        a file handler will automatically be created if one doesn't already exist.

        If you are manually launching toolkit, we recommend that you call
        this method to initialize logging to file early on in your setup.
        Calling it multiple times will not result in the information being
        written to multiple different files - only one file logger can
        exist per session.

        :param log_name: Name of logger to create. This will form the
                         filename of the log file. If you pass None, you
                         ensure that any existing base file handlers terminate
                         their logging.
        :returns: The name of the previous log_name that is being switched away from.
        """

        previous_log_name = self._std_file_handler_log_name
        log.debug("Switching file based std logger from %s to %s" % (previous_log_name, log_name))

        if self._std_file_handler:
            # there is already a log handler.
            # terminate previous one
            log.debug(
                "Tearing down existing log handler '%s' (%s)" % (previous_log_name, self._std_file_handler)
            )
            self._root_logger.removeHandler(self._std_file_handler)
            self._std_file_handler = None

        # store new log name
        self._std_file_handler_log_name = log_name

        if log_name:
            # set up a new handler

            # avoid cyclic references
            from .util import filesystem

            # set up logging root folder
            filesystem.ensure_folder_exists(self.log_folder)

            # generate log path
            log_file = os.path.join(
                self.log_folder,
                "%s.log" % filesystem.create_valid_filename(log_name)
            )


            # create a rotating log file with a max size of 18 megs -
            # zendesk's current max attachment limit is 20mb so
            # this should make all log files attachable to support tickets.
            self._std_file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=1024*1024*18,  # 18 MiB
                backupCount=0
            )

            # example:
            # 2016-04-25 08:56:12,413 [44862 DEBUG tank.log] message message
            formatter = logging.Formatter(
                "%(asctime)s [%(process)d %(levelname)s %(name)s] %(message)s"
            )

            self._std_file_handler.setFormatter(formatter)
            self._root_logger.addHandler(self._std_file_handler)

            # log the fact that we set up the log file :)
            log.debug("Writing to log standard log file %s" % log_file)

        # return previous log name
        return previous_log_name

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
# level set to INFO by default.
sgtk_root_logger.setLevel(logging.INFO)
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
