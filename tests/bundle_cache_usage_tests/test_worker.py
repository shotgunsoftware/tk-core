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
from sgtk.descriptor.bundle_cache_usage.writer import BundleCacheUsageWriter

from .test_base import TestBundleCacheUsageBase, Utils


class TestBundleCacheUsageWorker(TestBundleCacheUsageBase):
    """
    Tests the 'BundleCacheUsageWorker' class
    """

    EXPECTED_DEFAULT_DB_FILENAME = "bundle_usage.db"

    def setUp(self):
        super(TestBundleCacheUsageWorker, self).setUp()
        self._debug = False
        BundleCacheUsageWriter.delete_instance()

        TestBundleCacheUsageBase._create_test_bundle_cache(self.bundle_cache_root)

       # TODO: How do you get bundle_cache test path as opposed to what is returned by
        # LocalFileStorageManager.get_global_root(LocalFileStorageManager.CACHE)
        os.environ["SHOTGUN_HOME"] = self.bundle_cache_root

    def tearDown(self):
        #self.delete_db()
        # Necessary to force creation of another instance
        # being a singleton the class would not create a new database
        # if we are deleting it.
        BundleCacheUsageWriter.delete_instance()
        super(TestBundleCacheUsageWorker, self).tearDown()

    def _log_debug(self, msg):
        if self._debug:
            print("TestBundleCacheUsageWorker: %s" % (msg))

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
        w.queue_task(time.sleep, 0.001)
        time.sleep(0.1)
        w.queue_task(time.sleep, 0.001)
        time.sleep(0.1)
        w.queue_task(time.sleep, 0.001)
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
            w.queue_task(time.sleep, 0.001)
            count -= 1

        self._log_debug("test loop ended")
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
            w.queue_task(time.sleep, 0.01)
            count -= 1

        self._log_debug("test loop ended")
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
        #self.delete_db()
        BundleCacheUsageWriter.delete_instance()
        w = BundleCacheUsageWorker(self.bundle_cache_root)
        w.start()

        TASK_COUNT = 1000
        count = TASK_COUNT
        start_time = time.time()
        while count > 0:
            # self.assertFalse(w.task_available)
            w.log_usage("mssate")
            # self.assertTrue(w.task_available)
            # print("task_available: %s" % (w.task_available))
            count -= 1
            # print("count: %s" % (count))

        self._log_debug("test loop ended")
        elapsed_time = time.time() - start_time

        self.assertGreater(w.pending_count, 0, "Was expecting some incomplete tasks.")
        w.stop()
        self.assertEquals(w.completed_count, TASK_COUNT)
        self.assertEquals(w.pending_count, 0, "Was not expecting pending tasks after `stop`.")


