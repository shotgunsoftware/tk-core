# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Methods relating to the Path cache, a central repository where metadata about
all Tank items in the file system are kept.

"""

import os

import time
import threading
import Queue
from .writer import BundleCacheUsageWriter

class BundleCacheUsageWorker(threading.Thread):

    """
    References:
        https://docs.python.org/2/library/queue.html
        https://docs.python.org/2/library/threading.html
    """

    MAXIMUM_QUEUE_SIZE = 1024


    def __init__(self, bundle_cache_root):
        super(BundleCacheUsageWorker, self).__init__()
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

    #
    # Private methods
    # Running exclusively from the worker thread context
    #
    ###########################################################################

    def __log_usage(self, bundle_path):
        self._bundle_cache_usage.log_usage(bundle_path)

    def __consume_task(self):
        function, args, kwargs = self._tasks.get()
        if function:
            function(*args, **kwargs)
            self._log_debug("Consumed task")
        else:
            self._log_debug("Bad Consumed task")

        with self._member_lock:
            if self._pending_count > 0:
                self._pending_count -= 1
            self._completed_count += 1

    def run(self):
        self._log_debug("Starting worker thread")

        #  SQLite objects created in a thread can only be used in that same thread.
        self._bundle_cache_usage = BundleCacheUsageWriter(self._bundle_cache_root)

        # With the database created & opened above, let's queue a initial
        # task about checking for OLD bundles

        while not self._terminate_requested.is_set() or self.pending_count > 0:

            with self._member_lock:
                self._main_loop_count += 1

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

        self._log_debug("worker thread terminated")

    #
    # Protected methods
    # Can run from either threading contextes
    #
    ###########################################################################

    def _log_debug(self, msg):
        if self._debug:
            print("%s: %s" % (self.__class__.name, msg))

    #
    # Public methods & properties
    # Can run from either threading contextes
    #
    ###########################################################################

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
        self._log_debug("Requesting worker thread termination...")

        self._queued_signal.set()
        self._terminate_requested.set()
        self.join(timeout=timeout)

