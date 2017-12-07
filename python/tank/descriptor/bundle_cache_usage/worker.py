# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import time
import threading
import Queue
from threading import Event, Thread, Lock

from .writer import BundleCacheUsageWriter
from . import BundleCacheUsageLogger as log

class BundleCacheUsageWorker(threading.Thread):

    """
    References:
        https://docs.python.org/2/library/queue.html
        https://docs.python.org/2/library/threading.html
    """

    MAXIMUM_QUEUE_SIZE = 1024

    # keeps track of the single instance of the class
    __instance = None

    def __new__(cls, *args, **kwargs):
        """Ensures only one instance of the metrics queue exists."""

        # create the queue instance if it hasn't been created already
        if not cls.__instance:
            log.debug("__new__")

            # remember the instance so that no more are created
            singleton = super(BundleCacheUsageWorker, cls).__new__(cls, *args, **kwargs)
            singleton._lock = Lock()

            # The underlying collections.deque instance
            # singleton._queue = deque(maxlen=cls.MAXIMUM_QUEUE_SIZE)
            bundle_cache_root = args[0] if len(args)>0 else None
            cls.__instance = singleton
            cls.__instance.__initialized = False
            singleton.__init__(bundle_cache_root)

        return cls.__instance

    # TODO: find a better way
    @classmethod
    def delete_instance(cls):
        cls.__instance = None

    def __init__(self, bundle_cache_root):
        log.debug("__init__")
        super(BundleCacheUsageWorker, self).__init__()
        #TODO: returning would cause a silent non-usage of specified parameter
        if (self.__initialized): return
        self._terminate_requested = threading.Event()
        self._queued_signal = threading.Event()
        self._tasks = Queue.Queue()
        self._cv = threading.Condition()
        self._member_lock = threading.Condition()
        self._completed_count = 0
        self._main_loop_count = 0
        self._pending_count = 0
        self._debug = False
        self._bundle_cache_usage = None
        self._bundle_cache_root = bundle_cache_root
        self.__initialized = True

    #
    # Private methods
    # Running exclusively from the worker thread context
    #
    ###########################################################################

    def __log_usage(self, bundle_path):
        """

        :param bundle_path:
        """

        #
        # First check whether the specified path in contained in
        # the "bundle cache" path specified on class creation.
        #

        #
        # Second, truncate the received
        #
        #
        #
        # We can probably do both into a single line of code

        if self._bundle_cache_root in bundle_path:
            truncated_path = bundle_path.replace(self._bundle_cache_root, "")
            self._bundle_cache_usage.log_usage(truncated_path)
            log.debug2("truncated_path=%s" % (truncated_path))

    def __consume_task(self):
        function, args, kwargs = self._tasks.get()
        if function:
            function(*args, **kwargs)
            log.debug2("Consumed task")
        else:
            log.debug2("Bad Consumed task")

        with self._member_lock:
            if self._pending_count > 0:
                self._pending_count -= 1
            self._completed_count += 1

    def run(self):
        log.debug("Starting worker thread")

        #  SQLite objects created in a thread can only be used in that same thread.
        self._bundle_cache_usage = BundleCacheUsageWriter(self._bundle_cache_root)

        # With the database created & opened above, let's queue a initial
        # task about checking for OLD bundles

        while not self._terminate_requested.is_set() or self.pending_count > 0:

            # Wait and consume an item
            self._queued_signal.wait()
            while self.pending_count > 0:
                self.__consume_task()

            # When all tasks have been processed we need to reset Queue signal
            # so this loop is not consuming all CPU on a closed loop.
            # Clearing the signal will cause the wait() statement above to sleep
            # the thread until it is signaled again by queueing a new task.
            self._queued_signal.clear()

            self._log_debug("worker thread looping")

            with self._member_lock:
                self._main_loop_count += 1


    #
    # Protected methods
    # Can run from either threading contextes
    #
    ###########################################################################

    #
    # Public methods & properties
    # Can run from either threading contextes
    #
    ###########################################################################

    @property
    def bundle_cache_root(self):
        return self._bundle_cache_root

    @property
    def completed_count(self):
        """
        Returns how many tasks have been completed by the worker thread.

        NOTE: Indicative only, with the worker thread running,
        by the time the next instruction is executed the value might
        be already different.

        :return: an integer of the completed task count
        """
        with self._member_lock:
            return self._completed_count

    def log_usage(self, bundle_path):
        log.debug2("log_usage = %s" % (bundle_path))
        self.queue_task(self.__log_usage, bundle_path)

    @property
    def pending_count(self):
        """
        Returns how many tasks are in the queue, still pending.

        NOTE: Indicative only, with the worker thread running,
        by the time the next instruction is executed the value might
        be already different.

        :return: an integer of the currently still queued tasks count
        """
        with self._member_lock:
            return self._pending_count

    def queue_task(self, function, *args, **kwargs):
        with self._member_lock:
            self._pending_count += 1
        self._tasks.put((function, args, kwargs))
        self._tasks.task_done()
        self._queued_signal.set()

    def stop(self, timeout=10.0):
        log.debug("Requesting worker thread termination...")

        self._queued_signal.set()
        self._terminate_requested.set()
        self.join(timeout=timeout)

