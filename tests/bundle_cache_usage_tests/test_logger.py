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

import os
import time
from mock import patch

from sgtk.descriptor.bundle_cache_usage.database import BundleCacheUsageDatabase
from sgtk.descriptor.bundle_cache_usage.logger import BundleCacheUsageLogger
from sgtk.descriptor.bundle_cache_usage.errors import (
    BundleCacheUsageTimeoutError,
    BundleCacheUsageInvalidBundleCacheRootError
)

from .test_base import TestBundleCacheUsageBase


def log_debug(message):
    """ Single point global method to add extra printout during tests"""
    print("DEBUG: %s" % (message))


class TestBundleCacheUsageLogger(TestBundleCacheUsageBase):
    """
    Tests the 'BundleCacheUsageLogger' class
    """

    MAXIMUM_BLOCKING_TIME_IN_SECONDS = 0.25

    def setUp(self):
        super(TestBundleCacheUsageLogger, self).setUp()
        BundleCacheUsageLogger.delete_instance()

    def tearDown(self):
        BundleCacheUsageLogger.delete_instance()
        super(TestBundleCacheUsageLogger, self).tearDown()

    def assertIsWithinPct(self, test_value, expected_value, tolerance):
        """

        :param test_value: A float value to check
        :param expected_value:  A float value of what is expected
        :param tolerance: A float tolerance expressed in percentage [0.0, 100.0]
        """
        expected_value_pct = expected_value * tolerance / 100.0
        min_value = expected_value - expected_value_pct
        max_value = expected_value + expected_value_pct
        self.assertTrue((test_value >= min_value) and (test_value <= max_value))

    def test_create_instance_with_invalid_parameter(self):
        """
        Test initialization with an invalid parameter
        """
        with self.assertRaises(BundleCacheUsageInvalidBundleCacheRootError):
            BundleCacheUsageLogger.delete_instance()
            BundleCacheUsageLogger(None)

        with self.assertRaises(BundleCacheUsageInvalidBundleCacheRootError):
            BundleCacheUsageLogger.delete_instance()
            BundleCacheUsageLogger("non-existing-path")

        path_to_file = os.path.join(self._test_bundle_path, "info.yml")
        with self.assertRaises(BundleCacheUsageInvalidBundleCacheRootError):
            BundleCacheUsageLogger.delete_instance()
            BundleCacheUsageLogger(path_to_file)

    def test_create_delete_instance(self):
        """
        Test for possible lock-ups by measuring elaped time
        for each individual create/destroy attemps
        """

        count = 1000
        while count > 0:
            start_time = time.time()
            BundleCacheUsageLogger(self.bundle_cache_root)
            BundleCacheUsageLogger.delete_instance()
            elapsed_time = time.time() - start_time
            # Should pretty much be instant and 250ms is an eternity for a computer
            self.assertLess(elapsed_time,
                            self.MAXIMUM_BLOCKING_TIME_IN_SECONDS,
                            "Lock up detected")
            count -= 1

    def test_delete_instance(self):
        """
        Test that deleting_instance() method can be called multiple times
        """

        count = 1000
        while count > 0:
            start_time = time.time()

            BundleCacheUsageLogger(self.bundle_cache_root)
            BundleCacheUsageLogger.delete_instance()
            BundleCacheUsageLogger.delete_instance()
            BundleCacheUsageLogger.delete_instance()
            BundleCacheUsageLogger(self.bundle_cache_root)
            BundleCacheUsageLogger.delete_instance()
            BundleCacheUsageLogger.delete_instance()
            elapsed_time = time.time() - start_time
            # Should pretty much be instant and 250ms is an eternity for a computer
            self.assertLess(elapsed_time,
                            self.MAXIMUM_BLOCKING_TIME_IN_SECONDS,
                            "Lock up detected")
            count -= 1

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
            logger = BundleCacheUsageLogger(self.bundle_cache_root)
            logger.delete_instance()
            logger = None
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
            logger = BundleCacheUsageLogger(self.bundle_cache_root)
            logger.stop()
            logger.delete_instance()
            logger = None
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
            logger = BundleCacheUsageLogger(self.bundle_cache_root)
            logger.log_usage(self._test_bundle_path)
            logger.log_usage(self._test_bundle_path)
            logger.log_usage(self._test_bundle_path)
            logger.stop()
            logger = None
            elapsed_time = time.time() - start_time
            # Should pretty much be instant and 250ms is an eternity for a computer
            self.assertLess(elapsed_time, 0.25, "Lock up possibly detected")
            count -= 1

    def test_main_loop_wait(self):
        """
        Tests join/waiting for worker thread termintation.
        We queue a task that takes longer than default wait
        time to check for raised exception
        """
        BundleCacheUsageLogger.delete_instance()
        logger = BundleCacheUsageLogger(self.bundle_cache_root)
        # Queue the long task.
        logger._queue_task(time.sleep, 4)

        with self.assertRaises(BundleCacheUsageTimeoutError):
            logger.stop(2)

    def test_queue_task(self):
        """
        Tests submitting a bulk of simple & very short wait tasks and verify
        that all tasks have been executed and completed before the ending 'stop'
        method times out.
        """
        logger = BundleCacheUsageLogger(self.bundle_cache_root)

        TASK_COUNT = 1000
        count = TASK_COUNT
        while count > 0:
            logger._queue_task(time.sleep, 0.001)
            count -= 1

        self.log_debug("test loop ended")
        self.assertGreater(logger.pending_count, 0, "Was expecting some incomplete tasks.")
        logger.stop()
        self.assertEquals(logger.completed_count, TASK_COUNT)
        self.assertEquals(logger.pending_count, 0, "Was not expecting pending tasks after `stop`.")

    def test_queue_task_timing_out(self):
        """
        Tests submitting a bulk of simple & very short wait tasks and verify
        that we're able to exit due a timeout with some uncompleted tasks.
        """
        logger = BundleCacheUsageLogger(self.bundle_cache_root)

        TASK_COUNT = 1000
        count = TASK_COUNT
        while count > 0:
            logger._queue_task(time.sleep, 0.01)
            count -= 1

        self.log_debug("test loop ended")
        self.assertGreater(logger.pending_count, 0, "Was expecting some incomplete tasks.")

        # Forcing a shorter timeout
        # The timeout below is way shorter than 1000 * 0.01s = 10 seconds
        start_time = time.time()
        with self.assertRaises(BundleCacheUsageTimeoutError):
            logger.stop(2)
        elapsed_time = time.time() - start_time

        # Verify that the timeout is approx. 2.0 seconds
        self.assertGreaterEqual(elapsed_time, 1.9)
        self.assertLessEqual(elapsed_time, 2.1)

        # Verify that we do have pending tasks
        self.assertGreater(logger.pending_count, 0,
                           "We're expecting a worker timeout, there should be incompleted tasks.")

        # finish waiting, we know that those tasks will take longer than 2 seconds
        try:
            logger.delete_instance()
        except BundleCacheUsageTimeoutError:
            pass

    def test_queue_log_usage(self):
        """
        Tests performances of tracking a large number of descriptor through usage of the logger class.
        Since actual database accesses are done asynchronously logging usage on the main thread should
        be rather quick, completion of all of the database commits should be substantially longer.

        There should be at the very least a 10:1 ratio
        Development system was showing approximately à 36:0
        """

        logger = BundleCacheUsageLogger(self.bundle_cache_root)

        TASK_COUNT = 1000
        MINIMAL_EXPECTED_RATIO = 20
        count = TASK_COUNT
        start_time = time.time()
        while count > 0:
            logger.log_usage(self._test_bundle_path)
            count -= 1

        queuing_time = time.time() - start_time
        logger.stop(10)
        completing_all_tasks_time = time.time() - start_time
        ratio = completing_all_tasks_time / queuing_time

        self.log_debug("%s: queuing_time             : %ss" % (self._testMethodName, queuing_time))
        self.log_debug("%s: completing_all_tasks_time: %ss" % (self._testMethodName, completing_all_tasks_time))
        self.log_debug("%s: ratio : %s" % (self._testMethodName, ratio))
        self.assertEquals(logger.pending_count, 0,
                          "Was not expecting pending tasks after `stop`.")
        self.assertGreater(ratio, MINIMAL_EXPECTED_RATIO,
                           "Expecting at the very least a %s:1 radio between completing tasks and queuing them" % (
                            MINIMAL_EXPECTED_RATIO
                           ))

    def test_error_reporting_queue(self):
        """
        Test the error/exception reporting queue and methods

        Reference:
            http://cpython-test-docs.readthedocs.io/en/latest/library/unittest.mock.html
        """
        pass

    def helper_divide_a_by_b(self, a, b):
        return a / b

    def test_indirect_error_reporting_from_worker_thread(self):
        """
        Indirectly exercise the error/exception reporting from worker
        thread through usage of the 'log_usage' method through worker thread.

        Reference:
            http://cpython-test-docs.readthedocs.io/en/latest/library/unittest.mock.html
        """

        with patch("logging.Logger.error") as mocked_log_error:
            logger = BundleCacheUsageLogger(self.bundle_cache_root)

            # Queue non-problematic tasks
            logger._queue_task(self.helper_divide_a_by_b, 10, 1)
            time.sleep(0.25) # allow worker processing
            logger.log_usage(self._test_bundle_path)
            time.sleep(0.25)  # allow worker processing
            self.assertEquals(0, mocked_log_error.call_count)

            # Queue a task that will generate an exception
            logger._queue_task(self.helper_divide_a_by_b, 10, 0)
            time.sleep(0.25)  # allow worker processing
            logger.log_usage(self._test_bundle_path)
            time.sleep(0.25)  # allow worker processing
            self.assertEquals(1, mocked_log_error.call_count)

            # Again, but now with several errors
            mocked_log_error.reset_mock()
            logger._queue_task(self.helper_divide_a_by_b, 10, 0)
            logger._queue_task(self.helper_divide_a_by_b, 10, 0)
            logger._queue_task(self.helper_divide_a_by_b, 10, 0)
            time.sleep(0.25)  # allow worker processing
            logger.log_usage(self._test_bundle_path)
            time.sleep(0.25)  # allow worker processing
            self.assertEquals(3, mocked_log_error.call_count)

    def test_indirect_database_error_reporting_from_worker_thread(self):
        """
        Indirectly tests the database error/exception reporting from worker
        thread through usage of the 'log_usage' method through worker thread.

        Reference:
            http://cpython-test-docs.readthedocs.io/en/latest/library/unittest.mock.html
        """

        with patch("logging.Logger.error") as mocked_log_error:
            with patch(
                "sgtk.descriptor.bundle_cache_usage.database.BundleCacheUsageDatabase._create_main_table"
            ) as mocked_create_main_table:

                # Mocking 'BundleCacheUsageDatabase._create_main_table'
                # prevents creation of the main table and cause pretty
                # much all writes to fail.
                logger = BundleCacheUsageLogger(self.bundle_cache_root)
                self.assertEquals(1, mocked_create_main_table.call_count)

                # With database NOT having a main table
                # let's try logging some usage.
                logger.log_usage(self._test_bundle_path)
                time.sleep(0.25)  # allow worker processing

                # Now, the next call to 'log_usage' should trigger
                # splitting out the errors
                logger.log_usage(self._test_bundle_path)
                self.assertEquals(1, mocked_log_error.call_count)
                self.assertEquals(
                    "Unexpected error consuming task : no such table: bundles",
                    mocked_log_error.call_args_list[0][0][0]
                )

    def test_indirect_time_override_error_reporting_from_worker_thread(self):
        """
        Indirectly tests the database error/exception reporting from worker
        thread through usage of the 'log_usage' method through worker thread.

        Reference:
            http://cpython-test-docs.readthedocs.io/en/latest/library/unittest.mock.html
        """

        with patch("logging.Logger.error") as mocked_log_error:
            # Mocking 'BundleCacheUsageDatabase._create_main_table'
            # prevents creation of the main table and cause pretty
            # much all writes to fail.
            logger = BundleCacheUsageLogger(self.bundle_cache_root)

            # Assign an invalid timestamp
            os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE"] = "asgjdhasgjhdasd"

            # With database NOT having a main table
            # let's try logging some usage.
            logger.log_usage(self._test_bundle_path)
            time.sleep(0.25)  # allow worker processing

            # Now, the next call to 'log_usage' should trigger
            # splitting out the errors
            logger.log_usage(self._test_bundle_path)
            self.assertEquals(1, mocked_log_error.call_count)
            self.assertEquals(
                "Unexpected error consuming task : invalid literal for int() with base 10: 'asgjdhasgjhdasd'",
                mocked_log_error.call_args_list[0][0][0]
            )

    def test_singleton(self):
        """ Tests that multiple instantiations return the same object."""
        db1 = BundleCacheUsageLogger(self.bundle_cache_root)
        db2 = BundleCacheUsageLogger(self.bundle_cache_root)
        db3 = BundleCacheUsageLogger(self.bundle_cache_root)
        self.assertTrue(db1 == db2 == db3)

    def test_singleton_params(self):
        """ Tests multiple instantiations with different parameter values."""
        wk1 = BundleCacheUsageLogger(self.bundle_cache_root)
        bundle_cache_root1 = wk1.bundle_cache_root

        new_bundle_cache_root = os.path.join(self.bundle_cache_root, "another-level")
        os.makedirs(new_bundle_cache_root)
        wk2 = BundleCacheUsageLogger(new_bundle_cache_root)

        # The second 'instantiation' should have no effect.
        # The parameter used in the first 'instantiation'
        # should still be the same
        self.assertTrue(bundle_cache_root1 == wk2.bundle_cache_root)
