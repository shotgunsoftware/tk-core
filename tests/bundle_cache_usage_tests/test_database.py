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
from mock import patch, Mock, MagicMock

from .test_base import TestBundleCacheUsageBase, Utils

from sgtk.descriptor.bundle_cache_usage.database import BundleCacheUsageDatabaseEntry, BundleCacheUsageDatabase
from sgtk.descriptor.bundle_cache_usage.errors import BundleCacheUsageInvalidBundleCacheRootError


class TestBundleCacheUsageWriterBasicOperations(TestBundleCacheUsageBase):
    """
    Tests the basic database operations in a non-pipeline context:
        eg.: create table, an entry, update entry
    """

    MAIN_TABLE_NAME = "bundles"
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

    def test_create_instance_with_invalid_parameter(self):
        """
        Test initialization with an invalid parameter
        """
        with self.assertRaises(BundleCacheUsageInvalidBundleCacheRootError):
            BundleCacheUsageDatabase(None)

        with self.assertRaises(BundleCacheUsageInvalidBundleCacheRootError):
            BundleCacheUsageDatabase("some-invalid-path")

        path_to_file = os.path.join(self._test_bundle_path, "info.yml")
        with self.assertRaises(BundleCacheUsageInvalidBundleCacheRootError):
            BundleCacheUsageDatabase(path_to_file)

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

        # Pre Checks
        self.assertEquals(self.db.get_bundle_count(), 0)
        self.assertIsNone(self.db.get_bundle(self._test_bundle_path))

        # Add unused bundle
        now = int(time.time())
        with patch("time.time", return_value=now):
            self.db.add_unused_bundle(self._test_bundle_path)

        self.assertEquals(1, self.db.get_bundle_count())
        bundle = self.db.get_bundle(self._test_bundle_path)
        self.assertIsNotNone(bundle)
        self.assertEquals(0, bundle.usage_count)
        self.assertEquals(now, bundle.add_timestamp)
        self.assertEquals(now, bundle.last_usage_timestamp)

    def test_db_log_usage_basic(self):
        """
        Tests the logging basic usage is exception free

        NOTE: Database connection and initials setup is done in the setUp method
        """

        # Log some usage
        now = int(time.time())
        with patch("time.time", return_value=now) as mocked_time_time:
            self.db.log_usage(self._test_bundle_path)

        self.assertEquals(1, self.db.get_bundle_count())
        bundle = self.db.get_bundle(self._test_bundle_path)
        self.assertIsNotNone(bundle)
        self.assertEquals(1, bundle.usage_count)
        self.assertEquals(now, bundle.add_timestamp)
        self.assertEquals(now, bundle.last_usage_timestamp)

    def test_property_path(self):
        """
        Tests that the 'path' property returns the expected value even after database close
        """

        # Test after initial DB connect
        self.assertEquals(self.db.path, self.expected_db_path)

    def test_db_log_usage_for_None_entry(self):
        """
        Tests that log_usage method can handle a None parameter
        """

        # Log some usage
        self.db.log_usage(None)

        # Low level test for record count
        self.assertEquals(self.db.get_bundle_count(), 0, "Was not expecting a new entry from None")

    def test_db_log_usage_for_new_entry(self):
        """
        Tests the basic of logging an entry not already existing in the database
        """

        # Low level test for record count
        self.assertEquals(self.db.get_bundle_count(), 0)
        # Test before logging anything
        self.assertIsNone(self.db.get_bundle(self._test_bundle_path))

        # Log some usage
        self.db.log_usage(self._test_bundle_path)

        # Low level test for record count
        self.assertEquals(self.db.get_bundle_count(), 1)

        # Test after logging usage
        bundle = self.db.get_bundle(self._test_bundle_path)
        self.assertIsNotNone(bundle)
        self.assertEquals(1, bundle.usage_count)

    def test_db_log_usage_for_existing_entry(self):
        """
        Tests logging an existing entry
        """
        # Log some initial usage
        self.db.log_usage(self._test_bundle_path)
        self.db.log_usage(self._test_bundle_path)
        self.db.log_usage(self._test_bundle_path)

        # Low level test for record count, we're logging the same bundle name twice
        # We expect a single record still
        self.assertEquals(
            1,
            self.db.get_bundle_count(),
            "Was expecting a single row since we've logged the same entry."
        )

        # Test after logging usage
        bundle = self.db.get_bundle(self._test_bundle_path)
        self.assertIsNotNone(bundle)
        self.assertEquals(
            3,
            bundle.usage_count,
            "Was expecting a usage count of 3 since we've logged usage 3 times for same entry"
        )

    def test_logging_entry_with_special_characters(self):
        """
        Tests logging entries which might containt special characters
        """

        self.db.log_usage(os.path.join(self.app_store_root, "tk_super_duper", "my-version", "test.txt"))
        self.db.log_usage(os.path.join(self.app_store_root, "tk_électrique", "élève", "eôusterish"))
        self.db.log_usage(os.path.join(self.app_store_root, "tk_?_question", "marsk", "test.txt"))
        self.db.log_usage(os.path.join(self.app_store_root, "tk.duper", "my-version", "test.txt"))

        # Plus 2 more NOT in the bundle cache
        self.db.log_usage("Shotgun/some-packahe/2.22.2")
        self.db.log_usage("Shotgun/some-packahe/2.11.1")

        # Low level test for record count, we're logging the same bundle name twice
        # We expect a single record still
        self.assertEquals(self.db.get_bundle_count(), 4)

    def test_get_unused_bundles(self):
        """
        Tests the `get_unused_bundles` method
        """
        bundle_path_old = os.path.join(self.bundle_cache_root, "app_store", "tk-shell", "v0.5.4")
        bundle_path_new = os.path.join(self.bundle_cache_root, "app_store", "tk-shell", "v0.5.6")

        now = int(time.time())

        # Add a bundle 90 days ago
        ninety_days_ago = now - (90 * 24 * 3600)
        # Log some usage as 90 days ago
        with patch("time.time", return_value=ninety_days_ago):
            self.db.add_unused_bundle(bundle_path_old)
            self.db.add_unused_bundle(bundle_path_new)

        # Log old bundle as 60 days ago
        sixty_days_ago = now - (60 * 24 * 3600)
        with patch("time.time", return_value=sixty_days_ago):
            self.db.log_usage(bundle_path_old)

        # Log new bundle as now
        self.db.log_usage(bundle_path_new)

        # Get old bundle list
        bundle_list = self.db.get_unused_bundles(sixty_days_ago)
        self.assertIsNotNone(bundle_list)
        self.assertEquals(len(bundle_list), 1)

        # Now check properties of that old bundle
        bundle = bundle_list[0]
        self.assertTrue(bundle_path_old.endswith(bundle.path))
        self.assertEquals(ninety_days_ago, bundle.add_timestamp)
        self.assertEquals(sixty_days_ago, bundle.last_usage_timestamp)

    def test_delete_entry(self):
        """
        Tests the `delete_entry` method with both an existing and non-existing entries
        """

        # Verify initial DB properties
        self.assertIsNone(self.db.get_bundle(self._test_bundle_path))
        self.assertEquals(0, self.db.get_bundle_count())

        # Log some usage / add bundle
        self.db.log_usage(self._test_bundle_path)
        bundle = self.db.get_bundle(self._test_bundle_path)
        self.assertIsNotNone(bundle)
        self.assertEquals(1, bundle.usage_count)
        self.assertEquals(1, self.db.get_bundle_count())

        # Try deleting a non-existing entry
        non_existing_bundle = BundleCacheUsageDatabaseEntry(
            (
                "foOOOo-bar!",
                1513635533,
                1513635533 + 1000,
                1
            )
        )
        self.db.delete_entry(non_existing_bundle)
        self.assertEquals(self.db.get_bundle_count(), 1)

        # Create a 'fake' bundle entry, delete it,
        # and verify final DB properties
        existing_bundle = BundleCacheUsageDatabaseEntry(
            (
                self.db._truncate_path(self._test_bundle_path),
                1513635533,
                1513635533 + 1000,
                1
            )
        )
        self.db.delete_entry(existing_bundle)
        self.assertIsNone(self.db.get_bundle(self._test_bundle_path))
        self.assertEquals(self.db.get_bundle_count(), 0)

    def test_methods_with_non_existing_entry(self):
        """
        Tests methods with a non-existing entry
        """

        # See the `_create_test_bundle_cache` for available created test bundles
        # also see `TestBundleCacheUsageBase.setUp()
        bundle_path = self._test_bundle_path

        # Verify initial DB properties
        now = self.db._get_timestamp()
        bundle = self.db.get_bundle(bundle_path)
        self.assertIsNone(bundle)
        self.assertEquals(0, self.db.get_bundle_count())

        # Log some usage / add bundle
        self.db.log_usage(bundle_path)
        bundle = self.db.get_bundle(bundle_path)
        self.assertIsNotNone(bundle)
        self.assertEquals(1, bundle.usage_count)
        self.assertEquals(1, self.db.get_bundle_count())
        self.assertLessEqual(now, bundle.last_usage_timestamp)
        self.assertLessEqual(now, bundle.add_timestamp)

        non_existing_bundle_name = "foOOOo-bar!"
        self.db.log_usage(non_existing_bundle_name)
        bundle = self.db.get_bundle(non_existing_bundle_name)
        self.assertIsNone(bundle)
        self.assertEquals(1, self.db.get_bundle_count())

    def test_date_format(self):

        expected_format = "%A, %d. %B %Y %I:%M%p"
        now = int(time.time())

        # Add a bundle 90 days ago
        ninety_days_ago = now - (90 * 24 * 3600)
        ninety_days_ago_str = datetime.datetime.fromtimestamp(ninety_days_ago).strftime(expected_format)
        # Log some usage as 90 days ago
        with patch("time.time", return_value=ninety_days_ago) as mocked_time_time:
            self.db.add_unused_bundle(self._test_bundle_path)

        # Log usage 60 days ago
        sixty_days_ago = now - (60 * 24 * 3600)
        sixty_days_ago_str = datetime.datetime.fromtimestamp(sixty_days_ago).strftime(expected_format)
        with patch("time.time", return_value=sixty_days_ago) as mocked_time_time:
            self.db.log_usage(self._test_bundle_path)

        # Get old bundle list
        bundle = self.db.get_bundle(self._test_bundle_path)
        self.assertIsNotNone(bundle)
        self.assertTrue(self._test_bundle_path.endswith(bundle.path))
        self.assertEquals(ninety_days_ago, bundle.add_timestamp)
        self.assertEquals(ninety_days_ago_str, bundle.add_date)
        self.assertEquals(sixty_days_ago, bundle.last_usage_timestamp)
        self.assertEquals(sixty_days_ago_str, bundle.last_usage_date)

    def test_path_truncated(self):
        """
        Tests that tracked path are truncated & relative to the bundle cache root
        e.g.: we can combine both and test (afterward) that path actually exists.
        """
        self.db.log_usage(self._test_bundle_path)
        bundle = self.db.get_bundle(self._test_bundle_path)

        expected_truncated_path = bundle.path.replace(self.bundle_cache_root, "")

        self.assertEquals(expected_truncated_path, bundle.path)

    def test_SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE_usage(self):
        """
        Test use of the 'SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE'
        environment variable.
        """

        self.assertEquals(0, self.db.get_bundle_count())

        # Make sure override is disabled
        os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE"] = ""

        now = int(time.time())
        later = now + 1234
        with patch("time.time", return_value=now) as mocked_time_time:
            # Log some usage
            self.db.log_usage(self._test_bundle_path)

            bundle = self.db.get_bundle(self._test_bundle_path)
            self.assertIsNotNone(bundle)
            self.assertEquals(now, bundle.last_usage_timestamp)

            # Still with the mock active, let's make use of env. var. override
            os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE"] = str(later)

            self.db.log_usage(self._test_bundle_path)
            bundle = self.db.get_bundle(self._test_bundle_path)
            self.assertIsNotNone(bundle)
            self.assertEquals(later, bundle.last_usage_timestamp)

    def test_SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE_bad_usage(self):
        """
        Test usage of the 'SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE'
        environment variable with bad value.
        """

        self.assertEquals(0, self.db.get_bundle_count())

        # Make sure override is disabled
        os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE"] = ""

        now = int(time.time())
        with patch("time.time", return_value=now):
            # Log some usage
            self.db.log_usage(self._test_bundle_path)

            bundle = self.db.get_bundle(self._test_bundle_path)
            self.assertIsNotNone(bundle)
            self.assertEquals(now, bundle.last_usage_timestamp)

            # Still with the mock active, let's make use of env. var. override
            # with a non-convertable value and assert no exception or error
            os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE"] = "agsjhdgkasda"

            # Since the value cannot be converted, we expect an exception
            with self.assertRaises(ValueError):
                self.db.log_usage(self._test_bundle_path)



