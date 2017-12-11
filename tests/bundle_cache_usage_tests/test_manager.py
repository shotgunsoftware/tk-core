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
import unittest2

import sgtk
from .test_base import TestBundleCacheUsageBase, Utils
from sgtk.descriptor.bundle_cache_usage.manager import BundleCacheManager
from sgtk.descriptor.bundle_cache_usage.manager import BundleCacheManagerException, BundleCacheManagerDeletionException
from sgtk.descriptor.bundle_cache_usage.writer import BundleCacheUsageWriter
from tank_test.tank_test_base import TankTestBase, setUpModule

class TestBundleCacheManager(TestBundleCacheUsageBase):
    """
    Test basic and simpler methods
    """

    # The number of items (files and folder) in that fake tk-maya bundle
    EXPECTED_FILE_AND_FOLDER_COUNT = 9
    MAXIMUM_BLOCKING_TIME_IN_SECONDS = 0.25

    def setUp(self):
        super(TestBundleCacheManager, self).setUp()

       # TODO: How do you get bundle_cache test path as opposed to what is returned by
        # LocalFileStorageManager.get_global_root(LocalFileStorageManager.CACHE)
        os.environ["SHOTGUN_HOME"] = self.bundle_cache_root
        self._test_path = os.path.join(self.bundle_cache_root, "app_store", "tk-maya", "v0.8.3")
        self._manager = BundleCacheManager(self.bundle_cache_root)

    def tearDown(self):
        Utils.safe_delete(self.bundle_cache_root)
        BundleCacheManager.delete_instance()
        self._manager = None
        super(TestBundleCacheManager, self).tearDown()

    def test_create_delete_instance(self):
        """
        Test for possible lock-ups by measuring elaped time
        for each individual create/destroy attemps
        """
        count = 1000
        while count > 0:
            start_time = time.time()
            mgr = BundleCacheManager(self.bundle_cache_root)
            BundleCacheManager.delete_instance()
            elapsed_time = time.time() - start_time
            # Should pretty much be instant and 250ms is an eternity for a computer
            self.assertLess(elapsed_time,
                            TestBundleCacheManager.MAXIMUM_BLOCKING_TIME_IN_SECONDS,
                            "Lock up detected")
            count -= 1

    def test_get_filelist(self):
        """ Tests the `_get_filelist` method against a known fake bundle. """

        filelist = self._manager._get_filelist(self._test_path)
        self.assertEquals(len(filelist), TestBundleCacheManager.EXPECTED_FILE_AND_FOLDER_COUNT)

    def test_get_filelist_with_non_existing_path(self):
        """ Tests the `_get_filelist` method against a non-existing file path. """

        with self.assertRaises(BundleCacheManagerException):
            self._manager._get_filelist("bogus_file_path")

    def test_get_usage_count(self):

        # Check that we get an inital zero
        self.assertEquals(0, self._manager.get_usage_count(self._test_path))

        # Log some usage
        self._manager.log_usage(self._test_path)
        self._manager.log_usage(self._test_path)
        self._manager.log_usage(self._test_path)

        # Check that it got incremented
        start_time = time.time()
        self.assertEquals(3, self._manager.get_usage_count(self._test_path))
        elapsed_time = time.time() - start_time
        # Check that execution is near instant
        self.assertLess(elapsed_time,
                        TestBundleCacheManager.MAXIMUM_BLOCKING_TIME_IN_SECONDS,
                        "Method took unexpectedly long time to execute"
                        )

    def test_get_last_usage_date(self):

        USAGE_TOLERANCE_IN_SECONDS = 2

        # Check that we get an inital None
        self.assertIsNone(self._manager.get_last_usage_date(self._test_path))

        # Log some usage
        now_unix_timestamp = int(time.time())
        self._manager.log_usage(self._test_path)

        # Check that it's about now within USAGE_TOLERANCE_IN_SECONDS
        start_time = time.time()
        last_date = self._manager.get_last_usage_date(self._test_path)
        elapsed_time = time.time() - start_time
        # Check that execution is near instant
        self.assertLess(elapsed_time,
                        TestBundleCacheManager.MAXIMUM_BLOCKING_TIME_IN_SECONDS,
                        "Method took unexpectedly long time to execute"
                        )
        # Now check received value
        self.assertGreaterEqual(now_unix_timestamp, last_date)
        self.assertLess(last_date, now_unix_timestamp+USAGE_TOLERANCE_IN_SECONDS)


class TestBundleCacheManagerFindBundles(TestBundleCacheUsageBase):
    """
    Test walking the bundle cache searching or discovering bundles in the app_store
    """

    # The number of bundles in the test bundle cache
    EXPECTED_BUNDLE_COUNT = 18

    def setUp(self):
        super(TestBundleCacheManagerFindBundles, self).setUp()

       # TODO: How do you get bundle_cache test path as opposed to what is returned by
        # LocalFileStorageManager.get_global_root(LocalFileStorageManager.CACHE)
        os.environ["SHOTGUN_HOME"] = self.bundle_cache_root

    def tearDown(self):
        Utils.safe_delete(self.bundle_cache_root)
        BundleCacheManager.delete_instance()
        super(TestBundleCacheManagerFindBundles, self).tearDown()

    def test_walk_bundle_cache(self):
        """
        Tests & exercise the `_walk_bundle_cache` private method.
        The method is expected to find

        # The test structure created in the `_create_test_bundle_cache_structure`
        # See `_create_test_bundle_cache_structure`  documentation.

        """
        # Tests using the test bundle cache test structure created in test setUp()
        files = BundleCacheManager(self.bundle_cache_root).find_bundles()
        self.assertEquals(len(files), TestBundleCacheManagerFindBundles.EXPECTED_BUNDLE_COUNT)

    def test_walk_bundle_cache_non_existing_folder(self):
        """
        Test with a non existing folder and check that an exception is thrown
        """
        test_path = os.path.join(self.bundle_cache_root, "non-existing-folder")
        with self.assertRaises(ValueError):
            files = BundleCacheManager(test_path)


    def test_walk_bundle_cache_level_down(self):
        # Try again, starting from a few level down. Although there are info.yml
        # files to be found they should not be recognized as bundles.
        #
        # We're arbitrarly using 'tk-maya/v0.8.3' as base folder since it includes
        # extra info.yml file(s) found in the plugin subfolder.
        #
        test_path = os.path.join(self.bundle_cache_root, "app_store", "tk-maya")
        mgr = BundleCacheManager(test_path)
        files = mgr.find_bundles()
        self.assertEquals(len(files), 0)
        BundleCacheManager.delete_instance()

        test_path = os.path.join(self.bundle_cache_root, "app_store", "tk-maya", "v0.8.3")
        mgr = BundleCacheManager(test_path)
        files = mgr.find_bundles()
        self.assertEquals(len(files), 0)
        BundleCacheManager.delete_instance()

        test_path = os.path.join(self.bundle_cache_root, "app_store", "tk-maya", "v0.8.3", "plugins")
        mgr = BundleCacheManager(test_path)
        files = mgr.find_bundles()
        self.assertEquals(len(files), 0)

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
        files = BundleCacheManager(test_path).find_bundles()
        self.assertEquals(len(files), TestBundleCacheManagerFindBundles.EXPECTED_BUNDLE_COUNT)


class TestBundleCacheManagerParanoidDelete(TestBundleCacheUsageBase):
    """
    Test various deletion scenarios directly using the `_paranoid_delete method.
    """
    def setUp(self):
        super(TestBundleCacheManagerParanoidDelete, self).setUp()
        self._test_path = os.path.join(self.bundle_cache_root, "app_store", "tk-maya", "v0.8.3")
        self._manager = BundleCacheManager(self.bundle_cache_root)

    def tearDown(self):
        Utils.safe_delete(self.bundle_cache_root)
        BundleCacheManager.delete_instance()
        super(TestBundleCacheManagerParanoidDelete, self).tearDown()

    def test_paranoid_delete_files(self):
        """ Tests the `_paranoi_delete_files` method against a known fake bundle. """
        manager = BundleCacheManager(self.bundle_cache_root)
        filelist = BundleCacheManager._get_filelist(self._test_path)
        manager._paranoid_delete(filelist)

    def _helper_paranoid_delete_with_link(self, link_dir, use_hardlink):
        """
        Helper method for several of the `test_paranoi_delete_with_` methods.

        file`` method against a known fake bundle to which a hardlink
        to a file will be added. We expect the method to fail because we don't want to delete
        file or folder links.

        :param link_dir: test using link to a directory else a file
        :param use_hardlink: test using a hardlink else a symlink
        """

        # Setup paths for link creation
        base_path = os.path.join(self.bundle_cache_root,
                                 "app_store", "tk-maya", "v0.8.3", "plugins", "basic")

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

        # get a filelist
        filelist = self._manager._get_filelist(self._test_path)

        # Now test that an exception is thrown
        with self.assertRaises(BundleCacheManagerDeletionException):
            self._manager._paranoid_delete(filelist)

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

        filelist = self._manager._get_filelist(self._test_path)

        # delete a file that's in the above list
        manually_deleted_file = os.path.join(self.bundle_cache_root,
                                             "app_store", "tk-maya",
                                             "v0.8.3", "plugins", "basic", "some_file.txt")

        os.remove(manually_deleted_file)

        with self.assertRaises(BundleCacheManagerDeletionException):
            self._manager._paranoid_delete(filelist)

    def test_paranoid_delete_with_extra_file(self):
        """
        Tests the `_paranoi_delete_files` method against a known fake bundle to which an extra
        file is added (not in the file list). We expect the method to fail because it cannot
        delete the parent folder of that extra file.
        """

        filelist = self._manager._get_filelist(self._test_path)

        # Add an extra file
        extra_file = os.path.join(self.bundle_cache_root,
                                  "app_store", "tk-maya",
                                  "v0.8.3", "some_unexpected_extra_file.txt")
        Utils.write_bogus_data(extra_file)

        with self.assertRaises(BundleCacheManagerDeletionException):
            self._manager._paranoid_delete(filelist)


class TestBundleCacheManagerPurgeBundle(TestBundleCacheUsageBase):
    """
    Similar to the `TestBundleCacheManagerParanoidDelete` test class, this one
    exercise similat code at a slightly higher level as this now uses database entry.
    """

    def setUp(self):
        super(TestBundleCacheManagerPurgeBundle, self).setUp()

        # TODO: How do you get bundle_cache test path as opposed to what is returned by
        # LocalFileStorageManager.get_global_root(LocalFileStorageManager.CACHE)
        os.environ["SHOTGUN_HOME"] = self.bundle_cache_root

        self._test_path = os.path.join(self.bundle_cache_root, "app_store", "tk-maya", "v0.8.3")
        self._manager = BundleCacheManager(self.bundle_cache_root)

    def tearDown(self):
        Utils.safe_delete(self.bundle_cache_root)
        self._manager = None
        BundleCacheManager.delete_instance()
        super(TestBundleCacheManagerPurgeBundle, self).tearDown()

    def test_simple_bundle_purge(self):
        """
        Tests purging a normal, nothing special, app store bundle.
        """

        # Assert the test setup itself
        self.assertTrue(os.path.exists(self._test_path))
        self.assertEquals(0, self._manager.get_usage_count(self._test_path))
        self.assertIsNone(self._manager.get_last_usage_date(self._test_path))

        # Log some usage
        self._manager.log_usage(self._test_path)
        self.assertEquals(1, self._manager.get_usage_count(self._test_path))
        self.assertIsNotNone(self._manager.get_last_usage_date(self._test_path))

        # Purge it!
        self._manager._purge_bundle(self._test_path)

        # Now verify that neither files or database entry exist
        self.assertEquals(0, self._manager.get_usage_count(self._test_path))
        self.assertIsNone(self._manager.get_last_usage_date(self._test_path))
        self.assertFalse(os.path.exists(self._test_path))

        # Finaly, that the parent folder still exists
        test_path_parent = os.path.abspath(os.path.join(self._test_path, os.pardir))
        self.assertTrue(os.path.exists(test_path_parent))

    def test_purge_bundle_with_link_file(self):
        """
        Tests purging a bundle which magically grown an extra file.
        The purging process should abort and the database entry should NOT be deleted.
        """

        link_dir = False
        use_hardlink = False

        # Setup paths for link creation
        base_path = os.path.join(self.bundle_cache_root,
                                 "app_store", "tk-maya", "v0.8.3", "plugins", "basic")

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
        self.assertTrue(os.path.exists(self._test_path))
        self.assertEquals(0, self._manager.get_usage_count(self._test_path))
        self.assertIsNone(self._manager.get_last_usage_date(self._test_path))
        self.assertTrue(os.path.exists(dest_path))
        self.assertTrue(os.path.islink(dest_path))

        # Log some usage
        self._manager.log_usage(self._test_path)
        self.assertEquals(1, self._manager.get_usage_count(self._test_path))
        self.assertIsNotNone(self._manager.get_last_usage_date(self._test_path))

        # Purge the bundle
        self._manager._purge_bundle(self._test_path)

        # Now verify that the bundle root folder and database entry still exist
        self.assertEquals(1, self._manager.get_usage_count(self._test_path))
        self.assertIsNotNone(self._manager.get_last_usage_date(self._test_path))
        self.assertTrue(os.path.exists(self._test_path))
        self.assertTrue(os.path.exists(dest_path))
        self.assertTrue(os.path.islink(dest_path))

class TestBundleCacheUsageManagerSingleton(TestBundleCacheUsageBase):
    """
    Test that the class is really a singleton
    """

    def test_singleton(self):
        """ Tests that multile instantiations return the same object."""
        db1 = BundleCacheManager(self.bundle_cache_root)
        db2 = BundleCacheManager(self.bundle_cache_root)
        db3 = BundleCacheManager(self.bundle_cache_root)
        self.assertTrue(db1 == db2 == db3)

    def test_singleton_params(self):
        """ Tests multiple instantiations with different parameter values."""
        wk1 = BundleCacheManager(self.bundle_cache_root)
        bundle_cache_root1 = wk1.bundle_cache_root

        new_bundle_cache_root = os.path.join(self.bundle_cache_root, "another-level")
        os.makedirs(new_bundle_cache_root)
        wk2 = BundleCacheManager(new_bundle_cache_root)

        # The second 'instantiation' should have no effect.
        # The parameter used in the first 'instantiation'
        # should still be the same
        self.assertTrue(bundle_cache_root1 == wk2.bundle_cache_root)
