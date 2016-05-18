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
import weakref
from functools import wraps
from . import constants

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
        #
        # note - this init isn't currently threadsafe.
        #
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

            # collection of weak references to handlers
            # that were created via the log manager.
            instance._handlers = []

            # the root logger, created at code init
            instance._root_logger = logging.getLogger(constants.ROOT_LOGGER_NAME)

            # check the TK_DEBUG flag at startup
            # this controls the "global debug" state
            # in the log manager
            if constants.DEBUG_LOGGING_ENV_VAR in os.environ:
                log.debug(
                    "%s environment variable detected. Enabling debug logging." % constants.DEBUG_LOGGING_ENV_VAR
                )
                instance._global_debug = True
            else:
                instance._global_debug = False

            cls.__instance = instance

        return cls.__instance

    @staticmethod
    def get_logger(log_name):
        """
        Generates standard logger objects for Toolkit.

        If you want to add standard toolkit logging to your code,
        the easiest way is to include the following at the top of
        your python file::

            import sgtk
            logger = sgtk.LogManager.get_logger(__name__)

        This will pick up the module hierarchy of your code and
        parent it under the standard Toolkit logger.

        .. note:: This method is useful if you are writing scripts, tools or wrappers.
                  If you are developing a Toolkit app, framework or engine,
                  you typically want to use :meth:`sgtk.platform.get_logger`
                  for your logging.

        .. note:: To output logging to screen or to a console,
                  we recommend using the :meth:`initialize_custom_handler`
                  convenience method.

        :param log_name: Name of logger to create. This name will be parented under
                         the sgtk namespace. If the name begins with ``tank.``, it will
                         be automatically replaced with ``sgtk.``.
        :returns: Standard python logger.
        """
        if log_name.startswith("tank."):
            # replace tank
            log_name = "%s.%s" % (constants.ROOT_LOGGER_NAME, log_name[5:])
        else:
            # parent under root logger
            log_name = "%s.%s" % (constants.ROOT_LOGGER_NAME, log_name)

        return logging.getLogger(log_name)

    @staticmethod
    def log_timing(func):
        """
        Decorator that times and logs the execution of a method.

        Sometimes it is useful to log runtime statistics about
        how long time a certain method takes to execute. In the
        case of Toolkit, it is particularly helpful when debugging
        issues to do with I/O or cloud connectivity.

        If you have a method that for example connects to Shotgun to
        retrieve data, you can decorate it::

            @sgtk.LogManager.log_timing
            def my_shotgun_publish_method():
                '''
                Publishes lots of files to Shotgun
                '''
                # shotgun code here

        In the debug logs, timings will be written to the
        ``sgtk.stopwatch`` logger::

            [DEBUG sgtk.stopwatch.module] my_shotgun_publish_method: 0.633s

        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            time_before = time.time()
            try:
                response = func(*args, **kwargs)
            finally:
                time_spent = time.time() - time_before
                # log to special timing logger
                timing_logger = logging.getLogger(
                    "%s.%s" % (constants.PROFILING_LOG_CHANNEL, func.__module__)
                )
                timing_logger.debug(
                    "%s: %fs" % (func.__name__, time_spent)
                )
            return response
        return wrapper



    def _set_global_debug(self, state):
        """
        Sets the state of the global debug in toolkit.
        """
        self._global_debug = state
        if self._global_debug:
            new_log_level = logging.DEBUG
        else:
            log.debug("Disabling debug logging.")
            new_log_level = logging.INFO

        # process handlers
        for handler_weak_ref in self._handlers:
            handler = handler_weak_ref()
            if handler:
                handler.setLevel(new_log_level)

        # process backdoor logger
        if self.base_file_handler:
            self.base_file_handler.setLevel(new_log_level)

        # log notifications
        if self._global_debug:
            log.debug(
                "Debug logging enabled. To permanently enable it, "
                "set the %s environment variable." % constants.DEBUG_LOGGING_ENV_VAR
            )

    def _get_global_debug(self):
        """
        Controls the global debug flag in toolkit. Toggling this
        flag will affect all log handlers that have been created
        though :meth:`initialize_custom_handler`.

        .. note:: Debug logging is off by default.
                  If you want to permanently enable debug logging,
                  set the environment variable ``TK_DEBUG``.
        """
        return self._global_debug

    global_debug = property(_get_global_debug, _set_global_debug)

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

        .. note:: If you want to add a custom logging handler to the root logger,
                  we recommend using the :meth:`initialize_custom_handler` method.

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

    def initialize_custom_handler(self, handler=logging.StreamHandler()):
        """
        Convenience method that initializes a log handler
        and attaches it to the toolkit logging root.

        .. note:: If you want to display log messages inside a DCC,
                  implement :meth:`~sgtk.platform.Engine._emit_log_message`.

        .. note:: If :meth:`global_debug` is set to True, the handler created
                  will be set to debug level, otherwise it will be set to info level.

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
        # example: [DEBUG tank.log] message message
        formatter = logging.Formatter(
            "[%(levelname)s %(name)s] %(message)s"
        )

        handler.setFormatter(formatter)
        self._root_logger.addHandler(handler)

        if self.global_debug:
            handler.setLevel(logging.DEBUG)
        else:
            handler.setLevel(logging.INFO)

        # add it to our list of handlers, but as a
        # weak reference so that it can be destroyed
        # elsewhere (e.g. at engine shutdown)
        self._handlers.append(weakref.ref(handler))

        return handler

    def uninitialize_base_file_handler(self):
        """
        Uninitialize base file handler created with :meth:`initialize_base_file_handler`.

        :returns: The name of the previous log_name that is being switched away from,
                  None if no base logger was previously active.
        """
        if self._std_file_handler is None:
            base_log_name = None

        else:
            base_log_name = self._std_file_handler_log_name

            # there is a log handler, so terminate it
            log.debug(
                "Tearing down existing log handler '%s' (%s)" % (base_log_name, self._std_file_handler)
            )
            self._root_logger.removeHandler(self._std_file_handler)
            self._std_file_handler = None
            self._std_file_handler_log_name = None

        # return the previous base log name
        return base_log_name

    def initialize_base_file_handler(self, log_name):
        """
        Create a file handler and attach it to the stgk base logger.
        This will write a rotating log file to disk in a standard
        location and will capture all log messages passed through
        the log hierarchy.

        .. note:: Files will be written into the a location on disk
                  defined by :meth:`log_folder`.

        When you start an engine via the :meth:`sgtk.platform.start_engine` method,
        a file handler will automatically be created if one doesn't already exist.

        If you are manually launching toolkit, we recommend that you call
        this method to initialize logging to file early on in your setup.
        Calling it multiple times will not result in the information being
        written to multiple different files - only one file logger can
        exist per session.

        :param log_name: Name of logger to create. This will form the
                         filename of the log file.
        :returns: The name of the previous log_name that is being switched away from,
                  None if no base logger was previously active.
        """
        # shut down any previous logger
        previous_log_name = self.uninitialize_base_file_handler()

        log.debug("Switching file based std logger from %s to %s" % (previous_log_name, log_name))

        # store new log name
        self._std_file_handler_log_name = log_name

        # avoid cyclic references
        from .util import filesystem

        # set up logging root folder
        filesystem.ensure_folder_exists(self.log_folder)

        # generate log path
        log_file = os.path.join(
            self.log_folder,
            "%s.log" % filesystem.create_valid_filename(log_name)
        )

        # create a rotating log file with a max size of 5 megs -
        # this should make all log files easily attachable to support tickets.
        self._std_file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=1024*1024*5,  # 5 MiB
            backupCount=0
        )

        # set the level based on global debug flag
        if self.global_debug:
            self._std_file_handler.setLevel(logging.DEBUG)
        else:
            self._std_file_handler.setLevel(logging.INFO)

        # Set up formatter. Example:
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


# the logger for logging messages from this file :)
log = LogManager.get_logger(__name__)

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
# level set to DEBUG by default.
# this should not be changed, but any filtering
# should happen via log handlers
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
