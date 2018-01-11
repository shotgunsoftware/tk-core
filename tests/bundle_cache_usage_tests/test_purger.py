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

from tank_test.tank_test_base import setUpModule

import os
import time
import random
import sys
import unittest2 as unittest
from mock import patch

from .test_base import TestBundleCacheUsageBase

from sgtk.descriptor.bundle_cache_usage.database import BundleCacheUsageDatabase, BundleCacheUsageDatabaseEntry
from sgtk.descriptor.bundle_cache_usage.tracker import BundleCacheUsageTracker
from sgtk.descriptor.bundle_cache_usage.purger import BundleCacheUsagePurger
from sgtk.descriptor.bundle_cache_usage.errors import BundleCacheTrackingError


class TestBundleCacheUsagePurger(TestBundleCacheUsageBase):
    """
    Test basic and simpler methods
    """

    def setUp(self):
        super(TestBundleCacheUsagePurger, self).setUp()
        self._purger = BundleCacheUsagePurger()
        self.assertEquals(self.bundle_cache_root, self._purger._bundle_cache_root)

    def helper_stress_test(self, purger, tracker, database, bundle_list, iteration_count=100):
        """
        On each loop, operations are randomly determined.

        :param purger: an object of BundleCacheUsagePurger type to use for the test
        :param bundle_list: a list of bundle path to randomly choose from
        :param iteration_count: an int of the number of iteration of this set
        """
        bundle_count = len(bundle_list)

        while iteration_count > 0:

            # Randomly determine
            if random.randint(0, 1):
                bundle_path = bundle_list[random.randint(0, bundle_count - 1)]
                start_time = time.time()
                tracker.track_usage(bundle_path)
                # Check that execution is near instant
                self.assertLess(
                    time.time() - start_time,
                    self.WAIT_TIME_INSTANT,
                    "The 'track_usage' method took unexpectedly long time to execute"
                )

            if random.randint(0, 1):
                start_time = time.time()
                purger._bundle_count
                # Check that execution is near instant
                self.assertLess(
                    time.time() - start_time,
                    self.WAIT_TIME_MEDIUM,
                    "The 'get_bundle_count' method took unexpectedly long time to execute"
                )

            # only if equals 0
            if not random.randint(0, iteration_count):
                bundle_path = bundle_list[random.randint(0, bundle_count - 1)]
                start_time = time.time()
                fake_bundle_entry = BundleCacheUsageDatabaseEntry(
                    (
                        database._truncate_path(bundle_path),
                        1513635533,
                        1513635533 + 1000,
                        1
                    )
                )
                purger.purge_bundle(fake_bundle_entry)
                self.assertLess(
                    time.time() - start_time,
                    self.WAIT_TIME_LONG,
                    "The 'purge_bundle' method took unexpectedly long time to execute"
                )

            iteration_count -= 1

    def test_stressing_class(self):
        """
        Stress test using a semi-random using a more complete set of methods.
        """
        test_bundle_list = self._get_test_bundles(self.bundle_cache_root)

        count = 20
        while count > 0:
            tracker = BundleCacheUsageTracker()
            tracker.start()
            purger = BundleCacheUsagePurger()
            database = BundleCacheUsageDatabase()
            self.helper_stress_test(purger, tracker, database, test_bundle_list)
            BundleCacheUsageTracker.delete_instance()
            count -= 1

    def test_get_unused_bundles(self):
        """
        Tests the `get_unused_bundles` method
        """
        database = BundleCacheUsageDatabase()
        bundle_path_old = os.path.join(self.bundle_cache_root, "app_store", "tk-shell", "v0.5.4")
        bundle_path_new = os.path.join(self.bundle_cache_root, "app_store", "tk-shell", "v0.5.6")

        # Log some usage some time ago
        with patch("time.time", return_value=self._bundle_last_usage_time):
            database.track_usage(bundle_path_old)

        # Should be logged as the REAL now
        database.track_usage(bundle_path_new)

        # First we check that we can get both entries specifying zero-days
        bundle_list = self._purger.get_unused_bundles(0)
        self.assertIsNotNone(bundle_list)
        self.assertEquals(len(bundle_list), 2)

        # Now get the unused list using defaults
        bundle_list = self._purger.get_unused_bundles()

        # Test the method returns just one of the two entries
        self.assertIsNotNone(bundle_list)
        self.assertEquals(len(bundle_list), 1)

    def helper_test_ensure_database_initialized(self, use_mock):
        """
        Test database intialization through the Purger class.
        """

        database = BundleCacheUsageDatabase()

        self.assertEquals(0, database.bundle_count)
        self.assertFalse(self._purger._database.initialized)

        if use_mock:
            with patch("time.time", return_value=self._bundle_creation_time):
                self._purger.ensure_database_initialized()
                # We need to wait because the above call queues requests to a
                # worker thread. The requests are executed asynchronously.
                # If we we're to leave the patch code block soon, the mock
                # would terminate before all request be processes and we
                # would end up with unexpected timestamps.
                time.sleep(0.5)
        else:
            os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE"] = str(self._bundle_creation_time)
            self._purger.ensure_database_initialized()

            # Disable override
            os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE"] = ""

        self.assertEquals(self.FAKE_TEST_BUNDLE_COUNT, self._purger._bundle_count)
        self.assertTrue(self._purger._database.initialized)

        bundle_list = self._purger.get_unused_bundles()
        self.assertEquals(self.FAKE_TEST_BUNDLE_COUNT, len(bundle_list))

    def test_ensure_database_initialized(self):
        """
        Test database initialization through the Purger class.
        """
        self.helper_test_ensure_database_initialized(use_mock=True)

    def test_ensure_database_initialized_with_override(self):
        """
        Test database initialization with the use the override
        'SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE' environment variable
        """
        self.helper_test_ensure_database_initialized(use_mock=False)


class TestBundleCacheUsagePurgerFindBundles(TestBundleCacheUsageBase):
    """
    Test walking the bundle cache searching or discovering bundles in the app_store
    """

    def test_walk_bundle_cache(self):
        """
        Tests & exercise the `_walk_bundle_cache` private method.
        The method is expected to find

        # The test structure created in the `_create_test_bundle_cache_structure`
        # See `_create_test_bundle_cache_structure`  documentation.

        """
        # Tests using the test bundle cache test structure created in test setUp()
        files = BundleCacheUsagePurger()._find_app_store_bundles()
        self.assertEquals(len(files), self.FAKE_TEST_BUNDLE_COUNT)


class TestBundleCacheUsagePurgerPurgeBundle(TestBundleCacheUsageBase):
    """
    Similar to the `TestBundleCacheUsagePurgerParanoidDelete` test class, this one
    exercise similat code at a slightly higher level as this now uses database entry.
    """

    def setUp(self):
        super(TestBundleCacheUsagePurgerPurgeBundle, self).setUp()
        self._purger = BundleCacheUsagePurger()

    def tearDown(self):
        extra_bundle = os.path.join(self.bundle_cache_root, "app_store", "tk-maya", "v0.8.4")
        if os.path.exists(extra_bundle):
            os.remove(extra_bundle)

        super(TestBundleCacheUsagePurgerPurgeBundle, self).tearDown()

    def _helper_purge_bundle(self, test_bundle_path,
                             expect_test_bundle_path_deleted, expect_parent_folder_deleted,
                             expect_bundle_tracked=True,
                             expect_source_deleted=False,
                             source_path=None, dest_path=None, use_hardlink=False):
        """
        Helper method for the test_purge_bundle_* methods.

        .. NOTE: Relying on the PipelineConfig initializing worker thread

        :param test_bundle_path: a str of a test bundle path
        :param expect_test_bundle_path_deleted: a bool for testing that
        the bundle is expected to be deleted.
        :param expect_parent_folder_deleted: a boot that indicates that
        the bundle parent folder is expected to be deleted.
        :param source_path: a str source path to create a link/symlink
        :param dest_path: a str dest path to create a link/symlink
        :param use_hardlink: a boolean of whether to use hardlink
        """
        if source_path and dest_path:

            self.assertTrue(os.path.exists(source_path))

            # Create link
            if use_hardlink:
                os.link(source_path, dest_path)
            else:
                os.symlink(source_path, dest_path)

            self.assertTrue(os.path.exists(dest_path))
            self.assertTrue(os.path.islink(dest_path))

        self.assertTrue(os.path.exists(test_bundle_path))
        self.assertEquals(0, self._purger._bundle_count)

        # Add a database entry some time ago
        with patch("time.time", return_value=self._bundle_last_usage_time):
            # Relying on the PipelineConfig initializing worker thread
            BundleCacheUsageTracker.track_usage(test_bundle_path)
            time.sleep(self.WAIT_TIME_SHORT) # logging is async, we need to wait to endure operation is done
            if expect_bundle_tracked:
                self.assertEquals(1, self._purger._bundle_count)
            else:
                self.assertEquals(0, self._purger._bundle_count)

        if expect_bundle_tracked:
            # Get list and purge old bundles
            bundle_list = self._purger.get_unused_bundles()
            self.assertEquals(1, len(bundle_list))
            self._purger.purge_bundle(bundle_list[0])

        if source_path:
            self.assertEquals(expect_source_deleted, not os.path.exists(source_path))

        if expect_test_bundle_path_deleted:
            # Now verify that neither files or database entry exist
            self.assertEquals(0, self._purger._bundle_count)
            self.assertFalse(os.path.exists(test_bundle_path))

            # Finally, that the parent folder still exists
            test_path_parent = os.path.abspath(os.path.join(test_bundle_path, os.pardir))

            if expect_parent_folder_deleted:
                self.assertFalse(
                    os.path.exists(test_path_parent),
                    "Was expecting that the specified bundle parent folder would be deleted."
                )
            else:
                self.assertTrue(
                    os.path.exists(test_path_parent),
                    "Was expecting the specified bundle parent folder to exist still."
                )
        else:
            if expect_bundle_tracked:
                self.assertEquals(1, self._purger._bundle_count)
            else:
                self.assertEquals(0, self._purger._bundle_count)

            self.assertTrue(os.path.exists(test_bundle_path))

    def test_purge_bundle_simple(self):
        """
        Tests purging a normal, nothing special, app store bundle.
        """

        # The 'tk-maya' test bundle has only 1 version.
        # We expect the 'tk-maya' folder to be deleted.
        self._helper_purge_bundle(
            os.path.join(self.bundle_cache_root, "app_store", "tk-maya", "v0.8.3"),
            expect_test_bundle_path_deleted=True,
            expect_parent_folder_deleted=True
        )

    def test_purge_bundle_dual(self):
        """
        Tests purging a normal, nothing special, app store bundle.
        """

        # The `self._test_bundle_path` is "tk-shell" version v0.5.6.
        # The test setup includes 2 test versions of the `tk-shell` bundle.
        # We are expecting that the parent folder should still exist after.
        self._helper_purge_bundle(
            self._test_bundle_path,
            expect_test_bundle_path_deleted=True,
            expect_parent_folder_deleted=False
        )

    @unittest.skipIf(sys.platform.startswith("win"), "Skipped on Windows")
    def test_purge_bundle_with_linked_file_inside_app_store(self):
        """
        Tests purging a bundle which magically grown an extra file.
        The purging process should abort and the database entry should NOT be deleted.
        """

        test_bundle_path = os.path.join(self.bundle_cache_root, "app_store", "tk-maya", "v0.8.3")

        # Setup paths for link creation
        source_file = os.path.join(self.bundle_cache_root, "app_store", "tk-3dsmaxplus", "v0.4.1", "info.yml")
        dest_path = os.path.join(test_bundle_path, "plugins", "basic", "link_to_some_file.txt")

        self._helper_purge_bundle(
            test_bundle_path,
            expect_test_bundle_path_deleted=True,
            expect_parent_folder_deleted=True,
            expect_source_deleted=False,
            source_path=source_file,
            dest_path=dest_path,
            use_hardlink=False
        )

    @unittest.skipIf(sys.platform.startswith("win"), "Skipped on Windows")
    def test_purge_bundle_with_link_file_outside_app_store(self):
        """
        Tests purging a bundle which magically grown an extra file.
        The purging process should abort and the database entry should NOT be deleted.
        """

        test_bundle_path = os.path.join(self.bundle_cache_root, "app_store", "tk-maya", "v0.8.3")

        # Setup paths for link creation
        source_file = os.path.join(self._dev_bundle_path, "plugins", "basic", "some_file.txt")
        dest_path = os.path.join(test_bundle_path, "plugins", "basic", "link_to_file_outside_app_store.txt")

        self._helper_purge_bundle(
            test_bundle_path,
            expect_test_bundle_path_deleted=True,
            expect_parent_folder_deleted=True,
            expect_source_deleted=False,
            source_path=source_file,
            dest_path=dest_path,
            use_hardlink=False
        )

    @unittest.skipIf(sys.platform.startswith("win"), "Skipped on Windows")
    def test_purge_bundle_with_linked_bundle_inside_app_store(self):
        """
        Tests purging a bundle path which links to a bundle under the app_store folder.
        """

        test_bundle_path = os.path.join(self.bundle_cache_root, "app_store", "tk-maya", "v0.8.3")

        # Setup paths for link creation
        parent_path = os.path.abspath(os.path.join(test_bundle_path, os.pardir))
        source_path = os.path.join(test_bundle_path)
        dest_path = os.path.join(parent_path, "v0.8.4")

        self._helper_purge_bundle(
            test_bundle_path,
            expect_test_bundle_path_deleted=True,
            expect_parent_folder_deleted=True,
            expect_source_deleted=False,
            source_path=source_path,
            dest_path=dest_path,
            use_hardlink=False
        )

    @unittest.skipIf(sys.platform.startswith("win"), "Skipped on Windows")
    def test_purge_bundle_with_linked_bundle_outside_of_app_store(self):
        """
        Tests purging a bundle path which is a links to a bundle outside of the app_store/bundle cache folder.
        The bundle should not be tracked at all.
        """

        some_bundle_path = os.path.join(self.bundle_cache_root, "app_store", "tk-maya", "v0.8.3")

        # Setup paths for link creation
        source_path = os.path.join(some_bundle_path)
        dest_path = os.path.join(self._dev_bundle_path, "dev")

        self._helper_purge_bundle(
            dest_path,
            expect_test_bundle_path_deleted=False,
            expect_bundle_tracked=False,
            expect_parent_folder_deleted=False,
            expect_source_deleted=False,
            source_path=source_path,
            dest_path=dest_path,
            use_hardlink=False
        )
