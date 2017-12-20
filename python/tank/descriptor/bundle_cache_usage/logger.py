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
from threading import Event, Thread, Lock

from .errors import BundleCacheUsageTimeoutError
from .database import BundleCacheUsageDatabase as BundleCacheUsageDatabase
from . import BundleCacheUsageMyLogger as log


class BundleCacheUsageLogger(threading.Thread):

    """
    Update bundle cache usage in a simple single table database.
    To minimize performance impact, usage is logged using a
    fire-and-forget scheme to a worker thread.

    .. References::

        https://docs.python.org/2/library/queue.html
        https://docs.python.org/2/library/threading.html
    """

    MAXIMUM_QUEUE_SIZE = 1024
    DEFAULT_OP_TIMEOUT = 2 # in seconds
    DEFAULT_STOP_TIMEOUT = 10 # in seconds

    KEY_BUNDLE_COUNT = "bundle_count"
    KEY_LAST_USAGE_DATE = "last_usage_date"
    KEY_USAGE_COUNT = "usage_count"

    # keeps track of the single instance of the class
    __singleton_lock = threading.Lock()
    __singleton_instance = None

    def __new__(cls, *args, **kwargs):
        #
        # Based on tornado.ioloop.IOLoop.instance() approach.
        #
        # See:
        #   https://github.com/facebook/tornado
        #   https://gist.github.com/werediver/4396488
        #   https://en.wikipedia.org/wiki/Double-checked_locking
        #
        if not cls.__singleton_instance:
            log.debug_worker_threading("__new__")
            with cls.__singleton_lock:
                if not cls.__singleton_instance:
                    cls.__singleton_instance = super(BundleCacheUsageLogger, cls).__new__(cls, *args, **kwargs)
                    cls.__singleton_instance.__initialized = False

        return cls.__singleton_instance

    def __init__(self, bundle_cache_root):
        super(BundleCacheUsageLogger, self).__init__()
        # TODO: NICOLAS: returning would cause a silent non-usage of specified parameter
        if (self.__initialized):
            return
        self.__initialized = True
        log.debug_worker_threading("__init__")
        self._terminate_requested = threading.Event()
        self._queued_signal = threading.Event()
        self._tasks = Queue.Queue()
        self._member_lock = threading.Condition()
        self._completed_count = 0
        self._pending_count = 0
        # Make use of database class path validation.
        # This way we can catch and log such an error up-front
        # before the worker thread is actually started.
        BundleCacheUsageDatabase(bundle_cache_root)
        self._bundle_cache_root = bundle_cache_root
        self.start()

    @ classmethod
    def delete_instance(cls):
        """
        Safely lock the instance, stop the worker thread and set the instance to None
        """
        with cls.__singleton_lock:
            if cls.__singleton_instance:
                cls.__singleton_instance.stop()
                cls.__singleton_instance = None

    #
    # Private methods
    # Running exclusively from the worker thread context
    #
    ###########################################################################

    def __log_usage(self, bundle_path):
        """
        Update database's last usage date and usage count for the specified entry.

        .. note:: Invoked exclusively from the worker thread.

        :param bundle_path: A str of a bundle path
        """
        database = BundleCacheUsageDatabase(self._bundle_cache_root)
        database.log_usage(bundle_path)

    def __consume_task(self):
        """
        Execute a queued task.

        .. note:: Invoked exclusively from the worker thread.
        """
        try:
            method, args, kwargs = self._tasks.get()
            if method:
                method(*args, **kwargs)
        except Exception as e:
            log.error("UNEXPECTED Exception: %s " % (e))
            # TODO: NICOLAS: we're in a worker thread, find a way to report the error

        with self._member_lock:
            if self._pending_count > 0:
                self._pending_count -= 1
            self._completed_count += 1

    def run(self):
        """
        Implementation of threading.Thread.run()
        """

        log.debug_worker_threading("starting")

        try:
            while not self._terminate_requested.is_set() or self.pending_count > 0:

                # Pace the run loop by waiting and consuming as they are queued
                self._queued_signal.wait()

                # Note: the 'pending_count' property DOES wraps lock on _pending_count member
                while self.pending_count > 0:
                    self.__consume_task()

                # When all tasks have been processed we need to reset Queue signal
                # so this loop is not consuming all CPU.
                #
                # Clearing the signal will cause the `self._queued_signal.wait()` statement
                # above to sleep the thread until it is signaled again by queueing a new task
                # or requesting end of thread.
                self._queued_signal.clear()

        except Exception as e:
            log.error("UNEXPECTED Exception: %s " % (e))
            # TODO: NICOLAS: we're in a worker thread, find a way to report the error
            #      to main thread.
            # Why can't we log error to the regular logger?
            pass

        log.debug_worker_threading("terminated (%d tasks remaining)" % self.pending_count)

    #
    # Protected methods
    # Can run from either threading contextes
    #
    ###########################################################################

    def _queue_task(self, method, *args, **kwargs):
        """
        Add a task to the worker thread queue.

        :param method: method to call
        :param args: arguments to pass to the method
        :param kwargs: named arguments to pass to the method
        """
        with self._member_lock:
            self._pending_count += 1

        self._tasks.put((method, args, kwargs))
        self._tasks.task_done()
        self._queued_signal.set()

    #
    # Public methods & properties
    # Can run from either threading contextes
    #
    ###########################################################################

    @property
    def bundle_cache_root(self):
        """
        Returns the bundle cache path initially supplied in constructor.

        :return: A str path
        """
        return self._bundle_cache_root

    @property
    def completed_count(self):
        """
        Returns how many tasks have been completed by the worker thread.

        .. note:: Indicative only, with the worker thread running,
        by the time the next instruction is executed the value might
        be already different.

        :return: an integer of the completed task count
        """
        with self._member_lock:
            return self._completed_count

    @classmethod
    def log_usage(cls, bundle_path):
        """
        Queue a bundle cache usage database update.

        :param bundle_path: a str bundle path
        """
        with cls.__singleton_lock:
            if cls.__singleton_instance:
                cls.__singleton_instance._queue_task(cls.__singleton_instance.__log_usage, bundle_path)

    @property
    def pending_count(self):
        """
        Returns how many tasks are in the queue, still pending.

        .. note:: Indicative only, with the worker thread running,
        by the time the next instruction is executed the value might
        be already different.

        :return: an integer of the currently still queued tasks count
        """
        with self._member_lock:
            return self._pending_count

    def stop(self, timeout=DEFAULT_STOP_TIMEOUT):
        """
        Request worker thread termination and then wait for thread to finish.

        .. note:: An attempt is made to empty the task queued before exiting the worker thread.

        :param timeout: A float timeout in seconds
        """
        if self.isAlive():
            log.debug_worker_threading(
                "Requesting worker termination (pending tasks = %d) ..."  % (self.pending_count)
            )
            # Order is important below: signal thread termination FIRST!
            self._terminate_requested.set()
            self._queued_signal.set()
            self.join(timeout=timeout)
            # As join() always returns None, you must call isAlive() after
            # join() to decide whether a timeout happened
            if self.isAlive():
                raise BundleCacheUsageTimeoutError("Timeout waiting for worker thread to terminated.")



