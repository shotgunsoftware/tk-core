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

import os
import time
import random
import unittest2
from mock import patch

import sgtk
from .test_base import TestBundleCacheUsageBase, Utils

from sgtk.descriptor.bundle_cache_usage.database import BundleCacheUsageDatabase, BundleCacheUsageDatabaseEntry
from sgtk.descriptor.bundle_cache_usage.logger import BundleCacheUsageLogger
from sgtk.descriptor.bundle_cache_usage.purger import BundleCacheUsagePurger
from sgtk.descriptor.bundle_cache_usage.errors import (
    BundleCacheUsageError,
    BundleCacheUsageFileDeletionError,
    BundleCacheUsageInvalidBundleCacheRootError
)
from tank_test.tank_test_base import TankTestBase, setUpModule

class TestBundleCacheUsagePurger(TestBundleCacheUsageBase):
    """
    Test basic and simpler methods
    """

    MAXIMUM_BLOCKING_TIME_IN_SECONDS = 0.25

    def setUp(self):
        super(TestBundleCacheUsagePurger, self).setUp()
        self._purger = BundleCacheUsagePurger(self.bundle_cache_root)
        # Find possible `BundleCacheUsagePurger` singletonisation issue
        self.assertEquals(self.bundle_cache_root, self._purger.bundle_cache_root)

    def tearDown(self):
        super(TestBundleCacheUsagePurger, self).tearDown()

    def helper_stress_test(self, purger, logger, database, bundle_list, iteration_count=100):
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
                bundle_path = bundle_list[random.randint(0, bundle_count-1)]
                start_time = time.time()
                logger.log_usage(bundle_path)
                # Check that execution is near instant
                self.assertLess(time.time() - start_time,
                                TestBundleCacheUsagePurger.MAXIMUM_BLOCKING_TIME_IN_SECONDS,
                                "The 'log_usage' method took unexpectedly long time to execute")

            if random.randint(0, 1):
                start_time = time.time()
                purger.get_bundle_count()
                # Check that execution is near instant
                self.assertLess(time.time() - start_time,
                                TestBundleCacheUsagePurger.MAXIMUM_BLOCKING_TIME_IN_SECONDS,
                                "The 'get_bundle_count' method took unexpectedly long time to execute")

            # only if equals 0
            if not random.randint(0, iteration_count):
                bundle_path = bundle_list[random.randint(0, bundle_count-1)]
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
                # Check that execution is rather quick (2 times the blocking delay)
                self.assertLess(time.time() - start_time,
                                2*TestBundleCacheUsagePurger.MAXIMUM_BLOCKING_TIME_IN_SECONDS,
                                "The 'purge_bundle' method took unexpectedly long time to execute")

            iteration_count -= 1

    def test_stressing_class(self):
        """
        Stress test using a semi-random using a more complete set of methods.
        """
        test_bundle_list = self._get_test_bundles(self.bundle_cache_root)

        count = 20
        while count > 0:
            logger = BundleCacheUsageLogger(self.bundle_cache_root)
            purger = BundleCacheUsagePurger(self.bundle_cache_root)
            database = BundleCacheUsageDatabase(self.bundle_cache_root)
            self.helper_stress_test(purger, logger, database, test_bundle_list)
            BundleCacheUsageLogger.delete_instance()
            count -= 1

    def test_create_instance_with_invalid_parameter(self):
        """
        Test initialization with an invalid parameter
        """
        with self.assertRaises(BundleCacheUsageInvalidBundleCacheRootError):
            BundleCacheUsagePurger(None)

        with self.assertRaises(BundleCacheUsageInvalidBundleCacheRootError):
            BundleCacheUsagePurger("non-existing-path")

        path_to_file = os.path.join(self._test_bundle_path, "info.yml")
        with self.assertRaises(BundleCacheUsageInvalidBundleCacheRootError):
            BundleCacheUsagePurger(path_to_file)

    def test_get_filelist(self):
        """ Tests the `_get_filelist` method against a known fake bundle. """

        test_path = os.path.join(self.app_store_root, "tk-maya", "v0.8.3")
        filelist = self._purger._get_filelist(test_path)
        self.assertEquals(len(filelist), 9)

    def test_get_filelist_with_non_existing_path(self):
        """ Tests the `_get_filelist` method against a non-existing file path. """

        with self.assertRaises(BundleCacheUsageError):
            self._purger._get_filelist("bogus_file_path")

    def test_get_unused_bundles(self):
        """
        Tests the `get_unused_bundles` method
        """
        database = BundleCacheUsageDatabase(self.bundle_cache_root)
        bundle_path_old = os.path.join(self.bundle_cache_root, "app_store", "tk-shell", "v0.5.4")
        bundle_path_new = os.path.join(self.bundle_cache_root, "app_store", "tk-shell", "v0.5.6")

        now = int(time.time())
        ninety_days_ago = now - (90 * 24 * 3600)

        # Log some usage as 90 days ago
        with patch("time.time") as mocked:
            mocked.return_value = ninety_days_ago
            database.log_usage(bundle_path_old)

        # Should be logged as the REAL now
        database.log_usage(bundle_path_new)

        # First we check that we can get both entries specifying zero-days
        bundle_list = self._purger.get_unused_bundles(0)
        self.assertIsNotNone(bundle_list)
        self.assertEquals(len(bundle_list), 2)

        # Now get the unused list using defaults
        bundle_list = self._purger.get_unused_bundles()

        # Test the method returns just one of the two entries
        self.assertIsNotNone(bundle_list)
        self.assertEquals(len(bundle_list), 1)

    def helper_test_initial_populate_performed(self, use_mock):
        """
        Test the 'initial_populate_performed' property and possible side effect of
        relevant added code.
        """

        marker_name = self._purger._marker_name

        database = BundleCacheUsageDatabase(self.bundle_cache_root)

        self.assertEquals(0, database.get_bundle_count())
        self.assertIsNone(database.get_bundle(marker_name))
        self.assertFalse(self._purger.initial_populate_performed)

        now = int(time.time())
        ninety_days_ago = now - (90 * 24 * 3600)

        if use_mock:
            with patch("time.time", return_value=ninety_days_ago) as mocked_time_time:
                self._purger.initial_populate()
                # We need to wait because the above call queues requests to a
                # worker thread. The requests are executed asynchronously.
                # If we we're to leave the patch code block soon, the mock
                # would terminate before all request be processes and we
                # would end up with unexpected timestamps.
                time.sleep(0.5)
        else:
            os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE"] = str(ninety_days_ago)
            self._purger.initial_populate()

            # We need to wait because the above call queues requests to a
            # worker thread. The requests are executed asynchronously.
            # If we we're to leave the patch code block soon, the mock
            # would terminate before all request be processes and we
            # would end up with unexpected timestamps.
            time.sleep(0.5)

            # Disable override
            os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE"] = ""

        self.assertEquals(self.FAKE_TEST_BUNDLE_COUNT, self._purger.get_bundle_count())
        self.assertTrue(self._purger.initial_populate_performed)

        bundle_list = self._purger.get_unused_bundles()
        self.assertEquals(self.FAKE_TEST_BUNDLE_COUNT, len(bundle_list))
        # Finally, make sure the marker entry is not in the list
        for bundle in bundle_list:
            self.assertFalse(BundleCacheUsagePurger.INITIAL_DB_POPULATE_DONE_MARKER in bundle.path)

    def test_initial_populate_performed(self):
        """
        Test the 'initial_populate_performed' property and possible side effect of
        relevant added code.
        """
        self.helper_test_initial_populate_performed(use_mock=True)

    def test_initial_populate_performed_with_override(self):
        """
        Test the 'initial_populate_performed' property and possible side effect of
        relevant added code using the dedicated
        'SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE' env. variable to override
        logged elements.
        """
        self.helper_test_initial_populate_performed(use_mock=False)


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
        files = BundleCacheUsagePurger(self.bundle_cache_root)._find_bundles()
        self.assertEquals(len(files), self.FAKE_TEST_BUNDLE_COUNT)

    def test_walk_bundle_cache_non_existing_folder(self):
        """
        Test with a non existing folder and check that an exception is thrown
        """
        test_path = os.path.join(self.bundle_cache_root, "non-existing-folder")
        with self.assertRaises(BundleCacheUsageInvalidBundleCacheRootError):
            files = BundleCacheUsagePurger(test_path)


    def test_walk_bundle_cache_level_down(self):
        # Try again, starting from a few level down. Although there are info.yml
        # files to be found they should not be recognized as bundles.
        #
        # We're arbitrarly using 'tk-maya/v0.8.3' as base folder since it includes
        # extra info.yml file(s) found in the plugin subfolder.
        #
        test_path = os.path.join(self.bundle_cache_root, "app_store", "tk-maya")
        purger = BundleCacheUsagePurger(test_path)
        files = purger._find_bundles()
        self.assertEquals(len(files), 0)

        test_path = os.path.join(self.bundle_cache_root, "app_store", "tk-maya", "v0.8.3")
        purger = BundleCacheUsagePurger(test_path)
        files = purger._find_bundles()
        self.assertEquals(len(files), 0)

        test_path = os.path.join(self.bundle_cache_root, "app_store", "tk-maya", "v0.8.3", "plugins")
        purger = BundleCacheUsagePurger(test_path)
        files = purger._find_bundles()

    def test_walk_bundle_cache_level_up(self):
        """
        Tests & exercise the `_walk_bundle_cache` private method.
        The method is expected to find

        # The test structure created in the `_create_test_bundle_cache_structure`
        # See `_create_test_bundle_cache_structure`  documentation.

        """

        # Try again, starting a level up, the method should be able to find the app_store
        # folder and start from there.
        test_path = os.path.join(self.bundle_cache_root, os.pardir)
        files = BundleCacheUsagePurger(test_path)._find_bundles()
        self.assertEquals(len(files), self.FAKE_TEST_BUNDLE_COUNT)


class TestBundleCacheUsagePurgerParanoidDelete(TestBundleCacheUsageBase):
    """
    Test various deletion scenarios directly using the `_paranoid_delete method.
    """
    def setUp(self):
        super(TestBundleCacheUsagePurgerParanoidDelete, self).setUp()
        self._purger = BundleCacheUsagePurger(self.bundle_cache_root)

    def tearDown(self):
        Utils.safe_delete(self.bundle_cache_root)
        super(TestBundleCacheUsagePurgerParanoidDelete, self).tearDown()

    def _helper_paranoid_delete_with_link(self, link_dir, use_hardlink):
        """
        Helper method for several of the `test_paranoi_delete_with_` methods.

        file`` method against a known fake bundle to which a hardlink
        to a file will be added. We expect the method to fail because we don't want to delete
        file or folder links.

        :param link_dir: test using link to a directory else a file
        :param use_hardlink: test using a hardlink else a symlink
        """

        bundle_path = os.path.join(
            self.app_store_root,
            "tk-maya", "v0.8.3"
        )

        # Setup paths for link creation
        base_path = os.path.join(
            self.app_store_root,
            "tk-maya", "v0.8.3", "plugins", "basic"
        )

        if link_dir:
            source_file = os.path.join(base_path)
            dest_path = os.path.join(base_path, "link_to_some_dir")
        else:
            source_file = os.path.join(base_path, "some_file.txt")
            dest_path = os.path.join(base_path, "link_to_some_file.txt")

        # Create link
        if use_hardlink:
            os.link(source_file, dest_path)
        else:
            os.symlink(source_file, dest_path)

        # get a filelist
        filelist = self._purger._get_filelist(bundle_path)

        # Now test that an exception is thrown
        with self.assertRaises(BundleCacheUsageFileDeletionError):
            self._purger._paranoid_delete(filelist)

    def test_paranoid_delete_with_file_symlink(self):
        """
        Tests the `_paranoid_delete` method against a known fake bundle to which a symlink
        to a file is added.

        We expect the method to fail because we don't want to delete any links.
        """
        self._helper_paranoid_delete_with_link(link_dir=False, use_hardlink=False)

    # TODO: disabled, cannot determine of a  hardlink
    def _test_paranoid_delete_with_file_hardlink(self):
        """
        Tests the `_paranoid_delete` method against a known fake bundle to which a hardlink
        to a file is added.

        We expect the method to fail because we don't want to delete any links.
        """
        self._helper_paranoid_delete_with_link(link_dir=False, use_hardlink=True)

    def test_paranoid_delete_with_dir_symlink(self):
        """
        Tests the `_paranoid_delete` method against a known fake bundle to which a symlink
        to a folder is added.

        We expect the method to fail because we don't want to delete any links.
        """
        self._helper_paranoid_delete_with_link(link_dir=True, use_hardlink=False)

    # TODO: Disabled, need to be root to create dir links
    def _test_paranoid_delete_with_dir_hardlink(self):
        """
        Tests the `_paranoid_delete` method against a known fake bundle to which a hardlink
        to a folder is added.

        We expect the method to fail because we don't want to delete any links.
        """
        self._helper_paranoid_delete_with_link(link_dir=True, use_hardlink=True)

    def test_paranoid_delete_with_missing_file(self):
        """
        Tests the `_paranoi_delete_files` method against a known fake bundle to which a file
        file is deleted from the specified list of file. We expect the method to fail because
        it cannot delete a file specified in the list.
        """

        bundle_path = os.path.join(self.app_store_root, "tk-maya", "v0.8.3")

        filelist = self._purger._get_filelist(bundle_path)

        # delete a file that's in the above list
        manually_deleted_file = os.path.join(self.bundle_cache_root,
                                             "app_store", "tk-maya",
                                             "v0.8.3", "plugins", "basic", "some_file.txt")

        os.remove(manually_deleted_file)

        with self.assertRaises(BundleCacheUsageFileDeletionError):
            self._purger._paranoid_delete(filelist)

    def test_paranoid_delete_with_extra_file(self):
        """
        Tests the `_paranoi_delete_files` method against a known fake bundle to which an extra
        file is added (not in the file list). We expect the method to fail because it cannot
        delete the parent folder of that extra file.
        """

        bundle_path = os.path.join(self.app_store_root, "tk-maya", "v0.8.3")

        filelist = self._purger._get_filelist(bundle_path)

        # Add an extra file
        extra_file = os.path.join(self.bundle_cache_root,
                                  "app_store", "tk-maya",
                                  "v0.8.3", "some_unexpected_extra_file.txt")
        Utils.write_bogus_data(extra_file)

        with self.assertRaises(BundleCacheUsageFileDeletionError):
            self._purger._paranoid_delete(filelist)


class TestBundleCacheUsagePurgerPurgeBundle(TestBundleCacheUsageBase):
    """
    Similar to the `TestBundleCacheUsagePurgerParanoidDelete` test class, this one
    exercise similat code at a slightly higher level as this now uses database entry.
    """

    def setUp(self):
        super(TestBundleCacheUsagePurgerPurgeBundle, self).setUp()
        self._purger = BundleCacheUsagePurger(self.bundle_cache_root)

    def tearDown(self):
        BundleCacheUsageLogger.delete_instance()
        super(TestBundleCacheUsagePurgerPurgeBundle, self).tearDown()

    def test_simple_bundle_purge(self):
        """
        Tests purging a normal, nothing special, app store bundle.
        """

        # Comes from `TestBundleCacheUsageBase.setUp()`
        test_bundle_path = self._test_bundle_path

        # Assert the test setup itself
        self.assertTrue(os.path.exists(self._test_bundle_path))
        self.assertEquals(0, self._purger.get_bundle_count())

        # Log some usage
        logger = BundleCacheUsageLogger(self.bundle_cache_root)
        logger.start()
        time.sleep(0.5)  # logging is async, we need to wait to endure operation is done
        logger.log_usage(test_bundle_path)
        time.sleep(0.5) # logging is async, we need to wait to endure operation is done
        self.assertEquals(1, self._purger.get_bundle_count())

        # Purge it!
        bundle_list = self._purger.get_unused_bundles(0)
        self.assertEquals(1, len(bundle_list))
        self._purger.purge_bundle(bundle_list[0])

        # Now verify that neither files or database entry exist
        self.assertEquals(0, self._purger.get_bundle_count())
        self.assertFalse(os.path.exists(test_bundle_path))

        # Finally, that the parent folder still exists
        test_path_parent = os.path.abspath(os.path.join(test_bundle_path, os.pardir))
        self.assertTrue(os.path.exists(test_path_parent))

    def test_purge_bundle_with_link_file(self):
        """
        Tests purging a bundle which magically grown an extra file.
        The purging process should abort and the database entry should NOT be deleted.
        """

        link_dir = False
        use_hardlink = False

        test_bundle_path = os.path.join(self.bundle_cache_root, "app_store", "tk-maya", "v0.8.3")

        # Setup paths for link creation
        base_path = os.path.join(test_bundle_path, "plugins", "basic")

        if link_dir:
            source_file = os.path.join(base_path)
            dest_path = os.path.join(base_path, "extended")
        else:
            source_file = os.path.join(base_path, "some_file.txt")
            dest_path = os.path.join(base_path, "link_to_some_file.txt")

        # Create link
        if use_hardlink:
            os.link(source_file, dest_path)
        else:
            os.symlink(source_file, dest_path)

        # Assert the test setup itself
        self.assertTrue(os.path.exists(test_bundle_path))
        self.assertTrue(os.path.exists(dest_path))
        self.assertTrue(os.path.islink(dest_path))

        # Log some usage
        logger = BundleCacheUsageLogger(self.bundle_cache_root)
        logger.start()
        time.sleep(0.5)  # logging is async, we need to wait to endure operation is done
        logger.log_usage(test_bundle_path)
        time.sleep(0.5) # logging is async, we need to wait to endure operation is done
        self.assertEquals(1, self._purger.get_bundle_count())

        # Purge the bundle
        database = BundleCacheUsageDatabase(self.bundle_cache_root)
        fake_bundle_entry = BundleCacheUsageDatabaseEntry(
            (
                database._truncate_path(test_bundle_path),
                1513635533,
                1513635533 + 1000,
                1
            )
        )
        self._purger.purge_bundle(fake_bundle_entry)

        # Now verify that the bundle root folder and database entry still exist
        self.assertEquals(1, self._purger.get_bundle_count())
        self.assertTrue(os.path.exists(test_bundle_path))
        self.assertTrue(os.path.exists(dest_path))
        self.assertTrue(os.path.islink(dest_path))

