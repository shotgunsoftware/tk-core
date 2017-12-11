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
from . import USE_RELATIVE_PATH, LOG_LOG_USAGE, LOG_THREADING

class BundleCacheUsageWorker(threading.Thread):

    """
    References:
        https://docs.python.org/2/library/queue.html
        https://docs.python.org/2/library/threading.html
    """

    MAXIMUM_QUEUE_SIZE = 1024

    def __init__(self, bundle_cache_root):
        super(BundleCacheUsageWorker, self).__init__()
        log.debug_worker_threading("__init__")
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

    def __delete_entry(self, bundle_path, signal):
        """
        Worker thread only method deleting an entry from the database.
        :param bundle_path: a str of the database entry to delete
        :param signal: A threading.Event object created by original client from the main thread.
        """
        log.debug_worker("__delete_entry()")
        self._bundle_cache_usage.delete_entry(bundle_path)

        # We're done, signal caller!
        signal.set()

    def __get_entries_unused_since_last_days(self, days, signal, response):
        """
        Worker thread only method that queries the database for entries unused for the last N days.
        :param days:
        :param signal: A threading.Event object created by original client from the main thread.
        :param response: A list
        :return: indirectly returns a list through usage of the response variable
        """
        log.debug_worker("__get_entries_unused_since_last_days()")
        list = self._bundle_cache_usage._get_entries_unused_since_last_days(days)
        for item in list:
            response.append(item)

        # We're done, signal caller!
        signal.set()

    def __get_last_usage_date(self, bundle_path, signal, response):
        """
        Worker thread only method that queries the database for the last used entries unused for the last N days.
        :param signal: A threading.Event object created by original client from the main thread.
        :param response: A dict with a single "last_usage_date" key.
        :return: indirectly returns a list through usage of the response variable
        """
        last_usage_date = self._bundle_cache_usage.get_last_usage_date(bundle_path)
        log.debug_worker("__get_last_usage_date() = %s" % (last_usage_date))
        response["last_usage_date"] = last_usage_date

        # We're done, signal caller!
        signal.set()

    def __get_usage_count(self, bundle_path, signal, response):
        """
        Worker thread only method that queries the database for entries unused for the last N days.
        :param days:
        :param signal: A threading.Event object created by original client from the main thread.
        :param response: A tuple with a single value
        :return: indirectly returns the count value through usage of the response variable
        """
        count = self._bundle_cache_usage.get_usage_count(bundle_path)
        log.debug_worker("__get_usage_count() = %d" % (count))
        response["usage_count"] = count

        # We're done, signal caller!
        signal.set()

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
            if USE_RELATIVE_PATH:
                truncated_path = bundle_path.replace(self._bundle_cache_root, "")
                self._bundle_cache_usage.log_usage(truncated_path)
                log.debug_worker_hf("truncated_path=%s" % (truncated_path))
            else:
                self._bundle_cache_usage.log_usage(bundle_path)


    def __consume_task(self):
        """
        Invoked exclusively form the worker thread.
        """
        function, args, kwargs = self._tasks.get()
        if function:
            function(*args, **kwargs)
            log.debug_worker_hf("Consumed task")
        else:
            log.debug_worker_hf("Bad Consumed task")

        with self._member_lock:
            if self._pending_count > 0:
                self._pending_count -= 1
            self._completed_count += 1

    def run(self):
        log.debug_worker_threading("starting")

        try:
            #  SQLite objects created in a thread can only be used in that same thread.
            self._bundle_cache_usage = BundleCacheUsageWriter(self._bundle_cache_root)

            # With the database created & opened above, let's queue a initial
            # task about checking for existing bundles

            while not self._terminate_requested.is_set() or self.pending_count > 0:

                # Wait and consume an item, this is what is pacing the loop
                self._queued_signal.wait()

                # Note: the 'pending_count' property does wraps lock on _pending_count member
                while self.pending_count > 0:
                    self.__consume_task()

                # When all tasks have been processed we need to reset Queue signal
                # so this loop is not consuming all CPU on a closed loop.
                # Clearing the signal will cause the wait() statement above to sleep
                # the thread until it is signaled again by queueing a new task.
                self._queued_signal.clear()

                with self._member_lock:
                    self._main_loop_count += 1

        except Exception as e:
            log.error("UNEXPECTED Exception: %s " % (e))
            #TODO: we're in a worker thread, find a way to report the error
            #      to main thread.
            # Why can't we log error to the regular logger?
            pass

        finally:
            # Need to check that this was assigned, we might be comming
            # from an exception setting up the DB and bundle cache folder.
            if self._bundle_cache_usage:
                # Out of the loop, no longer expecting any operation on the DB
                # we can close it.
                self._bundle_cache_usage.close()

            log.debug_worker_threading("terminated (%d tasks remaining)" % self.pending_count)

    #
    # Protected methods
    # Can run from either threading contextes
    #
    ###########################################################################

    def _queue_task(self, function, *args, **kwargs):
        log.debug_worker_hf("_queue_task(...)")

        with self._member_lock:
            self._pending_count += 1
        self._tasks.put((function, args, kwargs))
        self._tasks.task_done()
        self._queued_signal.set()

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

    def delete_entry(self, bundle_path, timeout=2):
        """
        Blocking method which queues deletion of the specified entry from the database
        :param bundle_path: A str of a database entry to delete
        """
        signal = threading.Event()
        signal.clear()
        self._queue_task(self.__delete_entry, bundle_path, signal)
        signal.wait(timeout)

    def get_last_usage_date(self, bundle_path, timeout=2):
        """
        Blocking method that returns the date the specified bundle path was last used.

        :return: a datetime object of the last used date
        """
        signal = threading.Event()
        response = {"last_usage_date": None}
        signal.clear()
        self._queue_task(self.__get_last_usage_date, bundle_path, signal, response)
        signal.wait(timeout)

        return response.get("last_usage_date", None)

    def get_usage_count(self, bundle_path, timeout=2):
        """
        Blocking method that returns the number of time the specified bundle was referenced.

        :return: integer of the bundle usage count
        """
        signal = threading.Event()
        response = {"usage_count":0}
        signal.clear()
        self._queue_task(self.__get_usage_count, bundle_path, signal, response)
        signal.wait(timeout)

        return response.get("usage_count",0)

    def log_usage(self, bundle_path):
        log.debug_worker_hf("log_usage = %s" % (bundle_path))
        self._queue_task(self.__log_usage, bundle_path)

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

    def stop(self, timeout=10.0):
        log.debug("termination request ...")

        # Order is important below: signal thread termination FIRST!
        # Changing order below would cause a failure of the
        # TestBundleCacheManager.test_create_delete_instance test.
        self._terminate_requested.set()
        self._queued_signal.set()
        self.join(timeout=timeout)

    def get_entries_unused_since_last_days(self, days=60, timeout=2):
        """
        Blocking method that returns a list of entries that haven't been seen since the speciafied day count

        :return: A list of expired entries
        """

        signal = threading.Event()
        response = []
        signal.clear()
        self._queue_task(self.__get_entries_unused_since_last_days, days, signal, response)
        signal.wait(timeout)

        return response

