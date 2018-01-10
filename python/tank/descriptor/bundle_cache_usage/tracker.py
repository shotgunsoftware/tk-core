# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import threading
import Queue

from ... import LogManager
from .errors import BundleCacheTrackingTimeoutError
from .database import BundleCacheUsageDatabase as BundleCacheUsageDatabase


log = LogManager.get_logger(__name__)


class BundleCacheUsageTracker(threading.Thread):

    """
    Update bundle cache usage in a simple single table database.
    To minimize performance impact, usage is logged using a
    fire-and-forget scheme to a worker thread.

    .. References::

        https://docs.python.org/2/library/queue.html
        https://docs.python.org/2/library/threading.html
    """

    DEFAULT_STOP_TIMEOUT = 10 # in seconds

    MAX_CONSECUTIVE_ERROR_COUNT = 5 # consecutive error count before bailing out of worker loop

    KEY_BUNDLE_COUNT = "bundle_count"
    KEY_LAST_USAGE_DATE = "last_usage_date"
    KEY_USAGE_COUNT = "usage_count"

    # keeps track of the single instance of the class
    __singleton_lock = threading.Lock()
    __singleton_instance = None

    def __new__(cls, *args, **kwargs):
        """
        Create a singleton instance of the
        :class:`~sgtk.descriptor.bundle_cache_usage.tracker.BundleCacheUsageTracker` class.

        .. note:: For robustness, we use the double-locking mechanism.
                See https://en.wikipedia.org/wiki/Double-checked_locking
        """
        if not cls.__singleton_instance:
            with cls.__singleton_lock:
                if not cls.__singleton_instance:
                    cls.__singleton_instance = super(BundleCacheUsageTracker, cls).__new__(cls, *args, **kwargs)
                    cls.__singleton_instance._tasks = Queue.Queue()
                    cls.__singleton_instance._errors = Queue.Queue()

        return cls.__singleton_instance

    @ classmethod
    def delete_instance(cls, timeout=DEFAULT_STOP_TIMEOUT):
        """
        Safely lock the instance, stop the worker thread and set the instance to None
        :param timeout: A float timeout in seconds
        """
        with cls.__singleton_lock:
            if cls.__singleton_instance:
                cls.__singleton_instance.stop(timeout)
                cls.__singleton_instance = None

    #
    # Private methods
    # Running exclusively from the worker thread context
    #
    ###########################################################################

    def __log_error(self, exception, message):
        """
        Helper method that adds an exception and custom message to a queue allowing
        reporting of errors from the worker thread back into the main thread.

        :param exception: A
        :param message: a str custom message
        """
        self._errors.put((exception, message))
        self._errors.task_done()

    def __track_usage(self, bundle_path):
        """
        Update database's last usage date and usage count for the specified entry.

        .. note:: Invoked exclusively from the worker thread.

        :param bundle_path: A str of a bundle path
        """
        database = BundleCacheUsageDatabase()
        database.track_usage(bundle_path)

    def run(self):
        """
        Implementation of threading.Thread.run()
        """
        consecutive_error_count = 0
        try:
            while True:
                # Wait (block) until something is added to the queue
                method, args, kwargs = self._tasks.get()
                if method == "QUIT":
                    break

                if method:
                    try:
                        method(*args, **kwargs)
                        consecutive_error_count = 0
                    except Exception as e:
                        self.__log_error(e, "Unexpected error consuming task")
                        consecutive_error_count += 1
                    finally:
                        self._tasks.task_done()

                    if consecutive_error_count >= self.MAX_CONSECUTIVE_ERROR_COUNT:
                        # Too many consecutive errors, we bail out of the worker loop
                        self.__log_error(e, "Too many error in tracker worker thread, exiting thread, "\
                                "further tracking will be disabled.")
                        break

        except Exception as e:
            self.__log_error(e, "Unexpected exception in the worker run() method")

    #
    # Protected methods
    # Can run from either threading contextes
    #
    ###########################################################################

    def _check_for_queued_errors(self):
        """
        Checks errors queued from the worker thread and log them to logger from the main thread.

        .. note:: Called from main thread

        """
        while not self._errors.empty():
            exception, message = self._errors.get()
            log.error("%s : %s" % (message, exception))

    def _queue_task(self, method, *args, **kwargs):
        """
        Add a task to the worker thread queue.

        .. note:: Called from main thread

        :param method: method to call
        :param args: arguments to pass to the method
        :param kwargs: named arguments to pass to the method
        """
        self._check_for_queued_errors()
        self._tasks.put((method, args, kwargs))

    #
    # Public methods & properties
    # Can run from either threading contextes
    #
    ###########################################################################

    @classmethod
    def track_usage(cls, bundle_path):
        """
        Queue a bundle cache usage database update.

        :param bundle_path: a str bundle path
        """
        with cls.__singleton_lock:
            if cls.__singleton_instance:
                cls.__singleton_instance._queue_task(cls.__singleton_instance.__track_usage, bundle_path)
            else:
                log.warn("Bundle cache usage tracker instance not created, "\
                         "tracking of the '%s' bundle was not recorded." % (bundle_path))

    def stop(self, timeout=DEFAULT_STOP_TIMEOUT):
        """
        Request worker thread termination and then wait for thread to finish.

        .. note:: An attempt is made to empty the task queued before exiting the worker thread.

        :param timeout: A float timeout in seconds
        """
        if self.is_alive():
            log.debug("Requesting worker termination ..." )
            self._queue_task("QUIT", "User requested thread terminaison")
            self.join(timeout=timeout)
            # As join() always returns None, you must call isAlive() after
            # join() to decide whether a timeout happened
            if self.is_alive():
                raise BundleCacheTrackingTimeoutError("Timeout waiting for worker thread to terminated.")

            log.debug("Worker thread terminated cleanly.")



