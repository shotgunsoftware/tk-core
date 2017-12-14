# Copyright (c) 2017 Shotgun Software Inc.
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

from .exception import BundleCacheUsageTimeoutException
from .writer_sqlite import BundleCacheUsageSQLiteWriter as Writer
from . import BundleCacheUsageLogger as log


class BundleCacheUsageWorker(threading.Thread):

    """
    References:
        https://docs.python.org/2/library/queue.html
        https://docs.python.org/2/library/threading.html
    """

    MAXIMUM_QUEUE_SIZE = 1024
    DEFAULT_OP_TIMEOUT = 2 # in seconds
    DEFAULT_STOP_TIMEOUT = 10 # in seconds

    KEY_BUNDLE_COUNT = "bundle_count"
    KEY_LAST_USAGE_DATE = "last_usage_date"
    KEY_USAGE_COUNT = "usage_count"

    def __init__(self, bundle_cache_root):
        super(BundleCacheUsageWorker, self).__init__()
        log.debug_worker_threading("__init__")
        self._terminate_requested = threading.Event()
        self._database_created = threading.Event()
        self._queued_signal = threading.Event()
        self._tasks = Queue.Queue()
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

    def __add_unused_bundle(self, bundle_path):
        """
        Add a database entry initialised with a usage count of zero.
        :param bundle_path: A str of a bundle path
        """
        truncated_path = self._truncate_path(bundle_path)
        if truncated_path:
            now_unix_timestamp = self._get_timestamp()
            log.debug_worker("__add_unused_bundle('%s, %d')" % (truncated_path, now_unix_timestamp))
            self._bundle_cache_usage.add_unused_bundle(truncated_path, now_unix_timestamp)

    def __delete_entry(self, bundle_path, signal):
        """
        Worker thread only method deleting an entry from the database.
        :param bundle_path: a str of the database entry to delete
        :param signal: A threading.Event object created by original client from the main thread.
        """
        log.debug_worker("__delete_entry('%s')" %(bundle_path))
        self._bundle_cache_usage.delete_entry(bundle_path)

        # We're done, signal caller!
        signal.set()

    def __get_bundle_count(self, signal, response):
        """
        Worker thread only method that queries the database for entries unused for the last N days.
        :param signal: A threading.Event object created by original client from the main thread.
        :param response: A list
        :return: indirectly returns a dict  through usage of the response variable
        """
        count = self._bundle_cache_usage.get_bundle_count()
        log.debug_worker("__get_bundle_count() = %d" % (count))
        response[BundleCacheUsageWorker.KEY_BUNDLE_COUNT] = count

        # We're done, signal caller!
        signal.set()

    def __get_unused_bundles(self, since_days, signal, response):
        """
        Worker thread only method that queries the database for entries unused for the last N days.
        :param since_days:
        :param signal: A threading.Event object created by original client from the main thread.
        :param response: A list
        :return: indirectly returns a list through usage of the response variable
        """
        oldest_timestamp = self._get_timestamp() - (since_days * 24 * 3600)
        list = self._bundle_cache_usage._get_unused_bundles(oldest_timestamp)
        log.debug_worker("__get_unused_bundles(%d) count = %d" % (oldest_timestamp, len(list)))
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
        truncated_path = self._truncate_path(bundle_path)
        if truncated_path:
            log.debug_worker("__get_last_usage_date('%s')" %(truncated_path))
            last_usage_date = self._bundle_cache_usage.get_last_usage_date(truncated_path)
            response[BundleCacheUsageWorker.KEY_LAST_USAGE_DATE] = last_usage_date

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
        truncated_path = self._truncate_path(bundle_path)
        if truncated_path:
            count = self._bundle_cache_usage.get_usage_count(truncated_path)
            log.debug_worker("__get_usage_count('%s') = %d" % (truncated_path, count))
            response[BundleCacheUsageWorker.KEY_USAGE_COUNT] = count

        # We're done, signal caller!
        signal.set()

    def __log_usage(self, bundle_path):
        """
        Update database's last usage datefor the specified entry.
        :param bundle_path: A str of a bundle path
        """
        truncated_path = self._truncate_path(bundle_path)
        if truncated_path:
            now_unix_timestamp = self._get_timestamp()
            log.debug_worker("__log_usage('%s', %d)" % (truncated_path, now_unix_timestamp))
            self._bundle_cache_usage.log_usage(truncated_path, now_unix_timestamp)

    def __consume_task(self):
        """
        Invoked exclusively form the worker thread.
        """
        try:
            function, args, kwargs = self._tasks.get()
            if function:
                function(*args, **kwargs)
        except Exception as e:
            log.error("UNEXPECTED Exception: %s " % (e))
            #TODO: we're in a worker thread, find a way to report the error

        with self._member_lock:
            if self._pending_count > 0:
                self._pending_count -= 1
            self._completed_count += 1

    def __hit_main_loop_count(self):
        with self._member_lock:
            self._main_loop_count += 1

    def _truncate_path(self, bundle_path):
        """
        Helper method that returns a truncated path of the specified bundle path.
        The returned path is relative to the `self._bundle_cache_root` property.

        :param bundle_path:
        :return: A str truncated path if path exists in `self._bundle_cache_root` else None
        """

        if not bundle_path.startswith(self._bundle_cache_root):
            return None

        truncated_path = bundle_path.replace(self._bundle_cache_root, "")

        # also remove leading separator as it prevents os.path.join
        if truncated_path.startswith(os.sep):
            truncated_path = truncated_path[len(os.sep):]

        log.debug_worker_hf("truncated_path=%s" % (truncated_path))
        return truncated_path

    def run(self):
        """
        Implementation of threading.Thread.run()
        """

        log.debug_worker_threading("starting")

        try:
            #  The SQLite object can only be used in the thread it was created in.
            self._bundle_cache_usage = Writer(self._bundle_cache_root)
            self._database_created.set()

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

                self.__hit_main_loop_count()

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

    def _get_timestamp(self):
        """
        Utility method used
        :return:
        """

        timestamp_override = os.environ.get("SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE")
        if timestamp_override and len(timestamp_override):
            return int(timestamp_override)

        return int(time.time())

    def _queue_task(self, function, *args, **kwargs):
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

    def add_unused_bundle(self, bundle_path):
        """
        """
        self._queue_task(self.__add_unused_bundle, bundle_path)

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

    def delete_entry(self, bundle_path, timeout=DEFAULT_OP_TIMEOUT):
        """
        Blocking method which queues deletion of the specified entry from the database
        :param bundle_path: A str of a database entry to delete
        """
        signal = threading.Event()
        signal.clear()
        self._queue_task(self.__delete_entry, bundle_path, signal)
        if not signal.wait(timeout):
            raise BundleCacheUsageTimeoutException("delete_entry")

    def get_bundle_count(self, timeout=DEFAULT_OP_TIMEOUT):
        """
        Blocking method that returns the date the specified bundle path was last used.

        :return: a datetime object of the last used date
        """
        signal = threading.Event()
        response = {BundleCacheUsageWorker.KEY_BUNDLE_COUNT: 0}
        signal.clear()
        self._queue_task(self.__get_bundle_count, signal, response)

        # The return value is True unless a given timeout expired, in which case it is False.
        if not signal.wait(timeout):
            raise BundleCacheUsageTimeoutException("get_bundle_count")

        return response.get(BundleCacheUsageWorker.KEY_BUNDLE_COUNT, 0)

    def get_last_usage_date(self, bundle_path, timeout=DEFAULT_OP_TIMEOUT):
        """
        Blocking method that returns the date the specified bundle path was last used.

        :return: a datetime object of the last used date
        """
        signal = threading.Event()
        response = {BundleCacheUsageWorker.KEY_LAST_USAGE_DATE: None}
        signal.clear()
        self._queue_task(self.__get_last_usage_date, bundle_path, signal, response)
        if not signal.wait(timeout):
            raise BundleCacheUsageTimeoutException("get_last_usage_date")

        return response.get(BundleCacheUsageWorker.KEY_LAST_USAGE_DATE, None)

    def get_usage_count(self, bundle_path, timeout=DEFAULT_OP_TIMEOUT):
        """
        Blocking method that returns the number of time the specified bundle was referenced.

        :return: integer of the bundle usage count
        """
        signal = threading.Event()
        response = {BundleCacheUsageWorker.KEY_USAGE_COUNT: 0}
        signal.clear()
        self._queue_task(self.__get_usage_count, bundle_path, signal, response)
        if not signal.wait(timeout):
            raise BundleCacheUsageTimeoutException("get_usage_count")

        return response.get(BundleCacheUsageWorker.KEY_USAGE_COUNT, 0)

    def log_usage(self, bundle_path):
        """
        Increase the database usage count and access date for the specified bundle_path.
        If the entry was not in the database already, the usage count will be initialized to 1.
        The specified path is truncated and relative to the `bundle_cache_root` property.

        :param bundle_path: A str path to a bundle
        """
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

    def start(self, timeout=DEFAULT_OP_TIMEOUT):
        """
        Starts the worker thread and wait for a database connection to be ready.
        This is required in case an access is made very early after worker creation.

        :param timeout: A float maximum wait time in seconds
        """
        super(BundleCacheUsageWorker, self).start()
        if not self._database_created.wait(timeout):
            raise BundleCacheUsageTimeoutException("start")

    def stop(self, timeout=DEFAULT_STOP_TIMEOUT):

        log.debug("Requesting worker termination...")
        # Order is important below: signal thread termination FIRST!
        # Changing order below would cause a failure of the
        # TestBundleCacheManager.test_create_delete_instance test.
        self._terminate_requested.set()
        self._queued_signal.set()
        self.join(timeout=timeout)
        # TODO: Hwo to determine join timeout out?

    def get_unused_bundles(self, since_days, timeout=DEFAULT_OP_TIMEOUT):
        """
        Blocking method that returns a list of entries that haven't been seen since the speciafied day count

        :return: A list of expired entries
        """

        signal = threading.Event()
        response = []
        signal.clear()
        self._queue_task(self.__get_unused_bundles, since_days, signal, response)

        # The return value is True unless a given timeout expired, in which case it is False.
        if not signal.wait(timeout):
            raise BundleCacheUsageTimeoutException("get_bundle_count")

        return response

