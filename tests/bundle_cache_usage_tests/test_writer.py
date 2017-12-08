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

        if self._expected_db_path:
            if os.path.exists(self._expected_db_path):
                os.remove(self._expected_db_path)

        self._db = BundleCacheUsageWriter(self.bundle_cache_root)
        if os.path.exists(self._expected_db_path):
            self._expected_db_path

    def tearDown(self):
        # Necessary to force creation of another instance
        # being a singleton the class would not create a new database
        # if we are deleting it
        if self._expected_db_path:
            if os.path.exists(self._expected_db_path):
                os.remove(self._expected_db_path)

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

    def test_add_unused_bundle(self):
        """
        Tests that we can add a new bundle entry with an access count of zero
        """

        TEST_ENTRY_FAKE_PATH = "test-bundle"

        # Pre Checks
        self.assertEquals(self.db.bundle_count, 0, "Was not expecting any entry yet.")

        # Log something
        self.db.add_unused_bundle(TEST_ENTRY_FAKE_PATH)

        self.assertEquals(self.db.bundle_count, 1)
        self.assertEquals(self.db.get_usage_count(TEST_ENTRY_FAKE_PATH), 0)

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
        self.assertEquals(self.db.bundle_count, 0, "Was not expecting a new entry from None")

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
        self.db.log_usage("/Users/Marie-H�l�ne H�bert/databse.db")
        self.db.log_usage("~/Library/Cache/Shotgun/some-packahe/2.22.2")
        self.db.log_usage("~/Library/Cache/Shotgun/some-packahe/2.11.1")

        # Low level test for record count, we're logging the same bundle name twice
        # We expect a single record still
        self.assertEquals(self.db.bundle_count, 5, "Was expecting a single row since we've logged the same entry.")

    def test_get_entries_unused_since_last_days(self):
        """
        Tests the `_get_entries_unused_since_last_days` method
        """

        # Create a folder structure on disk but no entries are added to DB
        TestBundleCacheUsageBase._create_test_bundle_cache(self.bundle_cache_root)

        # See the `_create_test_bundle_cache` for available created test bundles

        bundle_path_old = os.path.join(self.bundle_cache_root, "app_store", "tk-shell", "v0.5.4")
        bundle_path_new = os.path.join(self.bundle_cache_root, "app_store", "tk-shell", "v0.5.6")

        SLEEP_TIME_IN_SECOND = 2
        # Log some usage / add bundle
        self.db.log_usage(bundle_path_old)
        # Wait some minimal time allow time to pass
        time.sleep(SLEEP_TIME_IN_SECOND)
        self.db.log_usage(bundle_path_new)


        # First we check that we can get both entries specifying zero-days
        bundle_list = self.db._get_entries_unused_since_last_days(0)
        self.assertIsNotNone(bundle_list)
        self.assertEquals(len(bundle_list), 2)

        # Now test getting entries older than SLEEP_TIME_IN_SECOND
        # Have to figure out how many days is 2 seconds
        days = 1.0 / (24.0 * 3600.0) * SLEEP_TIME_IN_SECOND

        bundle_list = self.db._get_entries_unused_since_last_days(days)

        # Test the method returns just one of the two entries
        self.assertIsNotNone(bundle_list)
        self.assertEquals(len(bundle_list), 1)


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

    def test_purge_bundle(self):
        """
        Tests the `purge_bundle` method
        """

        # Create a folder structure on disk but no entries are added to DB
        TestBundleCacheUsageBase._create_test_bundle_cache(self.bundle_cache_root)
        # See the `_create_test_bundle_cache` for available created test bundles
        bundle_path = os.path.join(self.bundle_cache_root,
                                   "app_store",
                                   "tk-shell",
                                   "v0.5.4")

        # Verify initial DB properties and actual folder
        self.assertEquals(self.db.get_usage_count(bundle_path), 0)
        self.assertEquals(self.db.bundle_count, 0)
        self.assertTrue(os.path.exists(bundle_path))
        self.assertTrue(os.path.isdir(bundle_path))

        # Log some usage / add bundle
        self.db.log_usage(bundle_path)
        self.assertEquals(self.db.get_usage_count(bundle_path), 1)
        self.assertEquals(self.db.bundle_count, 1)

        # Purge bundle and verify final DB properties and actual folder
        self.db.purge_bundle(bundle_path)
        self.assertEquals(self.db.get_usage_count(bundle_path), 0)
        self.assertEquals(self.db.bundle_count, 0)
        self.assertFalse(os.path.exists(bundle_path))
        self.assertFalse(os.path.isdir(bundle_path))

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