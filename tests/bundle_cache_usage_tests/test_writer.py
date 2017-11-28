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
import sgtk
import tempfile
import unittest2
import random
import shutil
import time

from .test_base import TestBundleCacheUsageBase, Utils

from sgtk.descriptor.bundle_cache_usage.writer import BundleCacheUsageWriter


class TestBundleCacheUsageWriterBasicOperations(TestBundleCacheUsageBase):
    """
    Tests the basic database operations in a non-pipeline context:
        eg.: create table, an entry, update entry

    NOTE: we don't need to inherit from 'tanTestBase' for testing basic DB operations
    Actually
    """

    MAIN_TABLE_NAME = "bundles"
    TEST_BUNDLE_PATH1 = "some-bundle-path1"
    PERF_TEST_ITERATION_COUNT = 100

    def setUp(self):
        super(TestBundleCacheUsageWriterBasicOperations, self).setUp()

        self._db = BundleCacheUsageWriter(self._temp_folder)
        if os.path.exists(self._expected_db_path):
            self._expected_db_path

    def tearDown(self):
        # Necessary to force creation of another instance
        # being a singleton the class would not create a new database
        # if we are deleting it.
        BundleCacheUsageWriter.delete_instance()
        super(TestBundleCacheUsageWriterBasicOperations, self).tearDown()

    ###################################################################################################################
    #
    # Test Methods
    #
    ###################################################################################################################

    def test_db_creation(self):
        """
        Test most basic database creation when db does not exists

        Simply verify there isn't any exception
        """
        db = BundleCacheUsageWriter(self._temp_folder)
        self.assertIsNotNone(db)
        self.assertIsInstance(db, BundleCacheUsageWriter, "Was expecting class type to be BundleCacheUsageWriter")

    def test_db_close(self):
        """
        Tests the `close` method and `connected` property

        NOTE: Database connection and initials setup is done in the setUp method
        """
        self.assertTrue(self.db.connected)
        self.db.close()
        self.assertFalse(self.db.connected)

    def test_db_main_table(self):
        """
        Tests that a main table gets created

        NOTE: Database connection and initials setup is done in the setUp method
        """
        ret = self.db._execute("SELECT name FROM main.sqlite_master WHERE type='table';")
        table_names = [x[0] for x in ret.fetchall()]
        self.assertEquals(len(table_names), 1, "Was expecting a single table to be created")
        self.assertEquals(table_names[0], TestBundleCacheUsageWriterBasicOperations.MAIN_TABLE_NAME)

    def test_bundle_cache_root_folder(self):
        self._db = BundleCacheUsageWriter(self.bundle_cache_root)
        self.assertEquals(self.bundle_cache_root, self._db.bundle_cache_root)

    def test_bundle_cache_root_folder(self):
        # Test auto-assignation based on usage of LocalFileStorageManager
        self._db = BundleCacheUsageWriter()
        self.assertEquals(self.bundle_cache_root, self._db.bundle_cache_root)

    def test_db_log_usage_basic(self):
        """
        Tests the logging basic usage is exception free

        NOTE: Database connection and initials setup is done in the setUp method
        """

        # Log some usage
        self.db.log_usage(TestBundleCacheUsageWriterBasicOperations.TEST_BUNDLE_PATH1)

    def test_property_path(self):
        """
        Tests that the 'path' property returns the expected value even after database close
        NOTE: Database connection and initials setup is done
        """

        # Test after initial DB connect
        self.assertEquals(self.db.path, self.expected_db_path)
        self.db.close()
        # Test after DB close
        self.assertEquals(self.db.path, self.expected_db_path)

    def test_db_log_usage_for_None_entry(self):
        """
        Tests that log_usage method can handle a None parameter
        NOTE: Database connection and initials setup is done in the setUp method
        """

        # Log some usage
        self.db.log_usage(None)

        # Low level test for record count
        self.assertEquals(self.db.bundle_count, 0, "Was not expecting an enrty since it was None.")

    def test_db_log_usage_for_new_entry(self):
        """
        Tests the basic of logging an entry not already existing in the database

        NOTE: Database connection and initials setup is done in the setUp method
        """

        BUNDLE_NAME = TestBundleCacheUsageWriterBasicOperations.TEST_BUNDLE_PATH1

        # Low level test for record count
        self.assertEquals(self.db.bundle_count, 0)
        # Test before logging anything
        self.assertEquals(self.db.get_usage_count(BUNDLE_NAME), 0)

        # Log some usage
        self.db.log_usage(BUNDLE_NAME)

        # Low level test for record count
        self.assertEquals(self.db.bundle_count, 1)
        # Test after logging usage
        self.assertEquals(self.db.get_usage_count(BUNDLE_NAME), 1)

    def test_db_log_usage_for_existing_entry(self):
        """
        Tests logging an existing entry

        NOTE: Database connection and initials setup is done in the setUp method
        """
        BUNDLE_NAME = TestBundleCacheUsageWriterBasicOperations.TEST_BUNDLE_PATH1

        self.assertEquals(self.db.get_usage_count(BUNDLE_NAME), 0)

        # Log some initial usage
        self.db.log_usage(BUNDLE_NAME)
        self.assertEquals(self.db.get_usage_count(BUNDLE_NAME), 1)

        # Log again
        self.db.log_usage(BUNDLE_NAME)
        self.assertEquals(self.db.get_usage_count(BUNDLE_NAME), 2)

        # ... and again
        self.db.log_usage(BUNDLE_NAME)
        self.assertEquals(self.db.get_usage_count(BUNDLE_NAME), 3)

        # Low level test for record count, we're logging the same bundle name twice
        # We expect a single record still
        self.assertEquals(self.db.bundle_count, 1, "Was expecting a single row since we've logged the same entry.")

        # Test after logging usage
        self.assertEquals(self.db.get_usage_count(BUNDLE_NAME), 3,
                          "Was expecting a usage count of 3 since we've logged usage twice for same entry")

    def test_logging_entry_with_special_characters(self):
        """
        Tests logging entries which might containt special characters

        NOTE: Database connection and initials setup is done in the setUp method
        """

        self.db.log_usage("C:\\Windows\Program Files\\test.txt")
        self.db.log_usage("/shotgun/workspace/databse.db")
        self.db.log_usage("/Users/Marie-Héléne Hébert/databse.db")
        self.db.log_usage("~/Library/Cache/Shotgun/some-packahe/2.22.2")
        self.db.log_usage("~/Library/Cache/Shotgun/some-packahe/2.11.1")

        # Low level test for record count, we're logging the same bundle name twice
        # We expect a single record still
        self.assertEquals(self.db.bundle_count, 5, "Was expecting a single row since we've logged the same entry.")

    def _helper_test_db_read_and_update_performance(self, path, iteration_count = PERF_TEST_ITERATION_COUNT):
        """

        :return:
        """

        loop_count = 0

        start_time = time.time()
        db = BundleCacheUsageWriter(path)
        while loop_count<iteration_count:
            bundle_test_name = "bundle-test-%03d" % (random.randint(0, 100))
            db.log_usage(bundle_test_name)
            db.commit()
            loop_count += 1

        db.close()
        elapsed = time.time() - start_time
        print("\nelapsed: %s" % (str(elapsed)))
        print("time per iteration: %s" % (str(elapsed/iteration_count)))

    def _test_db_read_and_update_performance_file(self):
        self._helper_test_db_read_and_update_performance(self._temp_folder)

    def _test_db_read_and_update_performance_memory(self):
        self._helper_test_db_read_and_update_performance(":memory:")

    def _test_db_read_and_update_performance(self):
        """

        :return:
        """

        ITERATION_COUNT = TestBundleCacheUsageWriterBasicOperations.PERF_TEST_ITERATION_COUNT
        iteration_count = 0

        start_time = time.time()
        while iteration_count<ITERATION_COUNT:
            db = BundleCacheUsageWriter(self._temp_folder)
            bundle_test_name = "bundle-test-%03d" % (random.randint(0, 100))
            db.log_usage(bundle_test_name)
            db.commit()
            db.close()

            iteration_count += 1

        elapsed = time.time() - start_time
        print("elapsed: %s" % (str(elapsed)))
        print("time per iteration: %s" % (str(elapsed/ITERATION_COUNT)))

    def _test_db_read_and_update_performance2(self):
        """

        :return:
        """

        ITERATION_COUNT = 40
        iteration_count = 0

        db = BundleCacheUsageWriter(self._temp_folder)
        start_time = time.time()
        while iteration_count<ITERATION_COUNT:
            #db = BundleCacheUsageWriter(self._temp_folder)
            bundle_test_name = "bundle-test-%03d" % (random.randint(0, 100))
            #bundle_test_name = "bundle-test-%04d" % (iteration_count)
            db.log_usage(bundle_test_name)
            #row_count = db.bundle_count
            iteration_count += 1

        db.commit()
        db.close()

        elapsed = time.time() - start_time
        #print("elapsed: %s" % (str(elapsed)))
        #print("time per iteration: %s" % (str(elapsed/ITERATION_COUNT)))


class TestBundleCacheUsageWriterSingleton(TestBundleCacheUsageBase):
    """
    Test that the class is really a singleton
    """
    def test_singleton(self):
        """ Tests that multile instantiations return the same object."""
        db1 = BundleCacheUsageWriter(self.bundle_cache_root)
        db2 = BundleCacheUsageWriter(self.bundle_cache_root)
        db3 = BundleCacheUsageWriter(self.bundle_cache_root)
        self.assertTrue(db1 == db2 == db3)

    def test_singleton_params(self):
        """ Tests multiple instantiations with different parameter values."""
        db1 = BundleCacheUsageWriter()
        path1 = db1.path

        new_bundle_cache_root = os.path.join(self.bundle_cache_root, "another-level")
        os.makedirs(new_bundle_cache_root)
        db2 = BundleCacheUsageWriter(new_bundle_cache_root)

        # The second 'instantiation' should have no effect.
        # The parameter used in the first 'instantiation'
        # should still be the same
        self.assertTrue(path1 == db2.path)