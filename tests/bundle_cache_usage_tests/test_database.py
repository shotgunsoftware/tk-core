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
import datetime

from .test_base import TestBundleCacheUsageBase, Utils

from sgtk.descriptor.bundle_cache_usage.database import BundleCacheUsageDatabase


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

        self._db = BundleCacheUsageDatabase(self.bundle_cache_root)
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
        db = BundleCacheUsageDatabase(self.bundle_cache_root)
        self.assertIsNotNone(db)
        self.assertIsInstance(
            db,
            BundleCacheUsageDatabase,
            "Was expecting class type to be BundleCacheUsageDatabase"
        )

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
        """
        ret = self.db._execute("SELECT name FROM main.sqlite_master WHERE type='table';")
        table_names = [x[0] for x in ret.fetchall()]
        self.assertEquals(len(table_names), 1, "Was expecting a single table to be created")
        self.assertEquals(table_names[0], TestBundleCacheUsageWriterBasicOperations.MAIN_TABLE_NAME)

    def test_bundle_cache_root_folder(self):
        self._db = BundleCacheUsageDatabase(self.bundle_cache_root)
        self.assertEquals(self.bundle_cache_root, self._db.bundle_cache_root)

    def test_add_unused_bundle(self):
        """
        Tests that we can add a new bundle entry with an access count of zero
        """

        TEST_ENTRY_FAKE_PATH = "test-bundle"

        # Pre Checks
        self.assertEquals(self.db.get_bundle_count(), 0, "Was not expecting any entry yet.")

        # Log something
        self.db.add_unused_bundle(TEST_ENTRY_FAKE_PATH, int(time.time()))

        self.assertEquals(self.db.get_bundle_count(), 1)
        self.assertEquals(self.db.get_usage_count(TEST_ENTRY_FAKE_PATH), 0)

    def test_db_log_usage_basic(self):
        """
        Tests the logging basic usage is exception free

        NOTE: Database connection and initials setup is done in the setUp method
        """

        # Log some usage
        self.db.log_usage(
            TestBundleCacheUsageWriterBasicOperations.TEST_BUNDLE_PATH1,
            int(time.time())
        )

    def test_property_path(self):
        """
        Tests that the 'path' property returns the expected value even after database close
        """

        # Test after initial DB connect
        self.assertEquals(self.db.path, self.expected_db_path)
        self.db.close()
        # Test after DB close
        self.assertEquals(self.db.path, self.expected_db_path)

    def test_db_log_usage_for_None_entry(self):
        """
        Tests that log_usage method can handle a None parameter
        """

        # Log some usage
        self.db.log_usage(None, int(time.time()))

        # Low level test for record count
        self.assertEquals(self.db.get_bundle_count(), 0, "Was not expecting a new entry from None")

    def test_db_log_usage_for_new_entry(self):
        """
        Tests the basic of logging an entry not already existing in the database
        """

        BUNDLE_NAME = TestBundleCacheUsageWriterBasicOperations.TEST_BUNDLE_PATH1

        # Low level test for record count
        self.assertEquals(self.db.get_bundle_count(), 0)
        # Test before logging anything
        self.assertEquals(self.db.get_usage_count(BUNDLE_NAME), 0)

        # Log some usage
        self.db.log_usage(BUNDLE_NAME, int(time.time()))

        # Low level test for record count
        self.assertEquals(self.db.get_bundle_count(), 1)
        # Test after logging usage
        self.assertEquals(self.db.get_usage_count(BUNDLE_NAME), 1)

    def test_db_log_usage_for_existing_entry(self):
        """
        Tests logging an existing entry
        """
        BUNDLE_NAME = TestBundleCacheUsageWriterBasicOperations.TEST_BUNDLE_PATH1

        self.assertEquals(self.db.get_usage_count(BUNDLE_NAME), 0)

        # Log some initial usage
        self.db.log_usage(BUNDLE_NAME, int(time.time()))
        self.assertEquals(self.db.get_usage_count(BUNDLE_NAME), 1)

        # Log again
        self.db.log_usage(BUNDLE_NAME, int(time.time()))
        self.assertEquals(self.db.get_usage_count(BUNDLE_NAME), 2)

        # ... and again
        self.db.log_usage(BUNDLE_NAME, int(time.time()))
        self.assertEquals(self.db.get_usage_count(BUNDLE_NAME), 3)

        # Low level test for record count, we're logging the same bundle name twice
        # We expect a single record still
        self.assertEquals(self.db.get_bundle_count(), 1, "Was expecting a single row since we've logged the same entry.")

        # Test after logging usage
        self.assertEquals(self.db.get_usage_count(BUNDLE_NAME), 3,
                          "Was expecting a usage count of 3 since we've logged usage twice for same entry")

    def test_logging_entry_with_special_characters(self):
        """
        Tests logging entries which might containt special characters
        """

        self.db.log_usage("C:\\Windows\Program Files\\test.txt", int(time.time()))
        self.db.log_usage("/shotgun/workspace/databse.db", int(time.time()))
        self.db.log_usage("/Users/Marie-Hélène Hébert/databse.db", int(time.time()))
        self.db.log_usage("~/Library/Cache/Shotgun/some-packahe/2.22.2", int(time.time()))
        self.db.log_usage("~/Library/Cache/Shotgun/some-packahe/2.11.1", int(time.time()))

        # Low level test for record count, we're logging the same bundle name twice
        # We expect a single record still
        self.assertEquals(self.db.get_bundle_count(), 5)

    def test_get_unused_bundles(self):
        """
        Tests the `get_unused_bundles` method
        """

        # See the `_create_test_bundle_cache` for available created test bundles

        bundle_path_old = os.path.join(self.bundle_cache_root, "app_store", "tk-shell", "v0.5.4")
        bundle_path_new = os.path.join(self.bundle_cache_root, "app_store", "tk-shell", "v0.5.6")

        now = int(time.time())

        # Add a bundle 90 days ago
        ninety_days_ago = now - (90 * 24 * 3600)
        ninety_days_ago_str = datetime.datetime.fromtimestamp(ninety_days_ago).isoformat()
        self.db.add_unused_bundle(bundle_path_old, ninety_days_ago)
        self.db.add_unused_bundle(bundle_path_new, ninety_days_ago)

        # Log old bundle as 60 days ago
        sixty_days_ago = now - (60 * 24 * 3600)
        sixty_days_ago_str = datetime.datetime.fromtimestamp(sixty_days_ago).isoformat()
        self.db.log_usage(bundle_path_old, sixty_days_ago)

        # Log new bundle as now
        self.db.log_usage(bundle_path_new, now)

        # Get old bundle list
        bundle_list = self.db.get_unused_bundles(sixty_days_ago)
        self.assertIsNotNone(bundle_list)
        self.assertEquals(len(bundle_list), 1)

        # Now check properties of that old bundle
        bundle = bundle_list[0]
        self.assertEquals(bundle_path_old, bundle.path)
        self.assertEquals(ninety_days_ago, bundle.add_timestamp)
        self.assertEquals(ninety_days_ago_str, bundle.add_date)
        self.assertEquals(sixty_days_ago, bundle.last_access_timestamp)
        self.assertEquals(sixty_days_ago_str, bundle.last_access_date)

    def test_delete_entry(self):
        """
        Tests the `delete_entry` method with both an existing and non-existing entries
        """

        # See the `_create_test_bundle_cache` for available created test bundles
        # also see `TestBundleCacheUsageBase.setUp()
        bundle_path = self._test_bundle_path

        # Verify initial DB properties
        self.assertEquals(self.db.get_usage_count(bundle_path), 0)
        self.assertEquals(self.db.get_bundle_count(), 0)

        # Log some usage / add bundle
        self.db.log_usage(bundle_path, int(time.time()))
        self.assertEquals(self.db.get_usage_count(bundle_path), 1)
        self.assertEquals(self.db.get_bundle_count(), 1)

        # Try deleting a non-existing entry
        self.db.delete_entry("foOOOo-bar!")
        self.assertEquals(self.db.get_usage_count("foOOOo-bar!"), 0)
        self.assertEquals(self.db.get_bundle_count(), 1)

        # Delete bundle and verify final DB properties
        self.db.delete_entry(bundle_path)
        self.assertEquals(self.db.get_usage_count(bundle_path), 0)
        self.assertEquals(self.db.get_bundle_count(), 0)

    def test_methods_with_non_existing_entry(self):
        """
        Tests methods with a non-existing entry
        """

        # See the `_create_test_bundle_cache` for available created test bundles
        # also see `TestBundleCacheUsageBase.setUp()
        bundle_path = self._test_bundle_path

        # Verify initial DB properties
        self.assertEquals(self.db.get_usage_count(bundle_path), 0)
        self.assertEquals(self.db.get_bundle_count(), 0)

        # Log some usage / add bundle
        self.db.log_usage(bundle_path, int(time.time()))
        self.assertEquals(self.db.get_usage_count(bundle_path), 1)
        self.assertEquals(self.db.get_bundle_count(), 1)

        non_existing_bundle_name = "foOOOo-bar!"
        self.db.delete_entry(non_existing_bundle_name)
        self.assertEquals(self.db.get_usage_count(non_existing_bundle_name), 0)
        self.assertEquals(self.db.get_last_usage_timestamp(non_existing_bundle_name), 0)



