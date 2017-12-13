# coding: latin-1
#
# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from tank_test.tank_test_base import TankTestBase, setUpModule

import sgtk
import unittest2
import os
import time

from sgtk.descriptor.bundle_cache_usage.worker import BundleCacheUsageWorker

from .test_base import TestBundleCacheUsageBase, Utils

DEBUG = True

def log_debug(message):
    if DEBUG:
        print("DEBUG: %s" % (message))


class TestBundleCacheUsageWorker(TestBundleCacheUsageBase):
    """
    Tests the 'BundleCacheUsageWorker' class
    """

    EXPECTED_DEFAULT_DB_FILENAME = "bundle_usage.db"

    def setUp(self):
        super(TestBundleCacheUsageWorker, self).setUp()
        TestBundleCacheUsageBase._create_test_bundle_cache(self.bundle_cache_root)

    def tearDown(self):
        super(TestBundleCacheUsageWorker, self).tearDown()

    def assertIsWithinPct(self, test_value, expected_value, tolerance ):
        """

        :param test_value: A float value to check
        :param expected_value:  A float value of what is expected
        :param tolerance: A float tolerance expressed in percentage [0.0, 100.0]
        """
        expected_value_pct = expected_value * tolerance / 100.0
        min_value = expected_value - expected_value_pct
        max_value = expected_value + expected_value_pct
        self.assertTrue((test_value >= min_value) and (test_value <= max_value))

    def test_stress_simple_start_stop(self):
        """
        Simple stress-Test for possible lock-ups while starting and stopping the
        worker thread.

        The test measures elaped time for each individual iteration and expect
        a near-instantaneous execution.
        """
        count = 1000
        while count > 0:
            start_time = time.time()
            worker = BundleCacheUsageWorker(self.bundle_cache_root)
            worker.start()
            worker.stop()
            worker = None
            elapsed_time = time.time() - start_time
            # Should pretty much be instant and 250ms is an eternity for a computer
            self.assertLess(elapsed_time, 0.25, "Lock up detected")
            count -= 1

    def test_stress_wait_worker_created_db(self):
        """
        Stress-Testing that a connection is ready after `start` is called.
        """
        count = 1000
        while count > 0:
            start_time = time.time()
            worker = BundleCacheUsageWorker(self.bundle_cache_root)
            worker.start()
            self.assertIsNotNone(worker._bundle_cache_usage.connected)
            worker.stop()
            worker = None
            elapsed_time = time.time() - start_time
            # Should pretty much be instant and 250ms is an eternity for a computer
            self.assertLess(elapsed_time, 0.25, "Lock up possibly detected")
            count -= 1

    def test_stress_start_stop_with_operations(self):
        """
        Stress-Test for possible lock-ups starting, issuing some operations and then
        and stopping the worker.

        The test measures elaped time for each individual iteration and expect
        a near-instantaneous execution.
        """
        count = 1000
        while count > 0:
            start_time = time.time()
            worker = BundleCacheUsageWorker(self.bundle_cache_root)
            worker.start()
            worker.log_usage(self._test_bundle_path)
            worker.log_usage(self._test_bundle_path)
            worker.log_usage(self._test_bundle_path)
            old_entries = worker.get_unused_bundles(0)
            worker.log_usage(self._test_bundle_path)
            worker.stop()
            worker = None
            elapsed_time = time.time() - start_time
            # Should pretty much be instant and 250ms is an eternity for a computer
            self.assertLess(elapsed_time, 0.25, "Lock up possibly detected")
            count -= 1

    def test_with_no_task(self):
        """
        Tests that the worker main loop is not looping
        """
        w = BundleCacheUsageWorker(self.bundle_cache_root)
        w.start()
        time.sleep(1)
        w.stop()
        self.assertEquals(w._main_loop_count, 1)

    def test_main_loop_wait(self):
        """
        Tests the worker main loop Queue wait(), set(), clear() usage
        When all tasks have been processed we need to reset Queue signal
        so the worker thread is not consumming all CPU on a closed loop.
        """
        w = BundleCacheUsageWorker(self.bundle_cache_root)
        w.start()
        w._queue_task(time.sleep, 0.001)
        time.sleep(0.1)
        w._queue_task(time.sleep, 0.001)
        time.sleep(0.1)
        w._queue_task(time.sleep, 0.001)
        time.sleep(0.1)
        w.stop()
        self.assertEquals(w._main_loop_count, 4)

    def test_queue_task(self):
        """
        Tests submitting a bulk of simple & very short wait tasks and verify
        that all tasks have been executed and completed before the ending 'stop'
        method times out.
        """
        w = BundleCacheUsageWorker(self.bundle_cache_root)
        w.start()

        TASK_COUNT = 1000
        count = TASK_COUNT
        while count > 0:
            w._queue_task(time.sleep, 0.001)
            count -= 1

        self.log_debug("test loop ended")
        self.assertGreater(w.pending_count, 0, "Was expecting some incomplete tasks.")
        w.stop()
        self.assertEquals(w.completed_count, TASK_COUNT)
        self.assertEquals(w.pending_count, 0, "Was not expecting pending tasks after `stop`.")

    def test_queue_task_timing_out(self):
        """
        Tests submitting a bulk of simple & very short wait tasks and verify
        that we're able to exit due a timeout with some uncompleted tasks.
        """
        w = BundleCacheUsageWorker(self.bundle_cache_root)
        w.start()

        TASK_COUNT = 10000
        count = TASK_COUNT
        while count > 0:
            w._queue_task(time.sleep, 0.01)
            count -= 1

        self.log_debug("test loop ended")
        self.assertGreater(w.pending_count, 0, "Was expecting some incomplete tasks.")

        # Forcing a shorter timeout
        # The timeout below is way shorter than 10000 * 0.01s = 100 seconds
        start_time = time.time()
        w.stop(2)
        elapsed_time = time.time() - start_time

        # Verify that the timeout is approx. 2.0 seconds
        self.assertGreaterEqual(elapsed_time, 1.9)
        self.assertLessEqual(elapsed_time, 2.1)

        # Verify that we do have pending tasks
        self.assertGreater(w.pending_count, 0,
                           "We're expecting a worker timeout, there should be incompleted tasks.")

    def test_queue_log_usage(self):
        """
        """
        w = BundleCacheUsageWorker(self.bundle_cache_root)
        w.start()

        TASK_COUNT = 1000
        count = TASK_COUNT
        start_time = time.time()
        while count > 0:
            w.log_usage(self._test_bundle_path)
            count -= 1

        self.log_debug("test loop ended")
        elapsed_time = time.time() - start_time

        self.assertGreater(w.pending_count, 0, "Was expecting some incomplete tasks.")
        w.stop()
        self.assertEquals(w.completed_count, TASK_COUNT)
        self.assertEquals(w.pending_count, 0, "Was not expecting pending tasks after `stop`.")

    def test_log_usage_truncated(self):
        """
        Tests that tracked path are truncated & relative to the bundle cache root
        e.g.: we can combine both and test (afterward) that path actually exists.
        """
        worker = BundleCacheUsageWorker(self.bundle_cache_root)
        worker.start()
        worker.log_usage(self._test_bundle_path)
        # TODO: missing assert statement ???
        worker.stop()

    def test_get_unused_bundles(self):

        """
        Test basic usage of `get_entries_unused_since_last_days` asynchronous method.
        """
        worker = BundleCacheUsageWorker(self.bundle_cache_root)
        worker.start()
        # log something

        time.sleep(2)
        entries = worker.get_unused_bundles(20)

        for entry in entries:
            print "entry = %s" % (entry)

    def test_get_unused_bundles_timing_out(self):
        """
        Tests that the  'get_entries_unused_since_last_days' asynchronous call does timeout
        by simply not starting the worker thread.
        """
        worker = BundleCacheUsageWorker(self.bundle_cache_root)

        expected_timeout = 1.0
        start_time = time.time()
        entries = worker.get_unused_bundles(since_days=20, timeout=expected_timeout)
        elapsed_time = time.time() - start_time
        self.assertIsWithinPct(elapsed_time, expected_timeout,10)
        self.assertIsNotNone(entries)
        self.assertTrue(len(entries) == 0)

class TestDatabasePerformanceThroughWorker(TestBundleCacheUsageBase):
    """
    Tests database access performance through usage of the 'BundleCacheUsageWorker' class
    """

    def test_queue_log_usage(self):
        """
        Tests performances of tracking a large number of descriptor through usage of the worker class.
        Since actual database accesses are done asynchronously logging usage on the main thread should
        be rather quick, completion of all of the database commits should be substantially longer.

        There should be at the very least a 10:1 ratio
        Development system was showing approximately à 36:0
        """

        # Create a folder structure on disk but no entries are added to DB
        TestBundleCacheUsageBase._create_test_bundle_cache(self.bundle_cache_root)
        # See the `_create_test_bundle_cache` for available created test bundles

        w = BundleCacheUsageWorker(self.bundle_cache_root)
        w.start()

        TASK_COUNT = 1000
        MINIMAL_EXPECTED_RATIO = 20
        count = TASK_COUNT
        start_time = time.time()
        while count > 0:
            w.log_usage(self._test_bundle_path)
            count -= 1

        queuing_time = time.time() - start_time
        w.stop(10)
        completing_all_tasks_time = time.time() - start_time
        ratio = completing_all_tasks_time/queuing_time

        self.log_debug("%s: queuing_time             : %ss" % (self._testMethodName, queuing_time))
        self.log_debug("%s: completing_all_tasks_time: %ss" % (self._testMethodName, completing_all_tasks_time))
        self.log_debug("%s: ratio : %s" % (self._testMethodName, ratio))
        self.assertEquals(w.pending_count, 0,
                          "Was not expecting pending tasks after `stop`.")
        self.assertGreater(ratio,MINIMAL_EXPECTED_RATIO,
                           "Expecting at the very least a %s:1 radio between completing tasks and queuing them" % (
                            MINIMAL_EXPECTED_RATIO
                           ))

