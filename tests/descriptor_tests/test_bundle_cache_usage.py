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

from sgtk.descriptor.bundle_cache_usage import BundleCacheUsage

class Utils(object):
    """
    A collection of miscelaneous non-specific methods
    Used throughout this module.
    """

    @classmethod
    def touch(cls, path):
        """
        Reference: https://stackoverflow.com/a/12654798/710183

        :param path:
        """
        dirs = os.path.dirname(path)

        if not os.path.exists(dirs):
            os.makedirs(dirs)

        with open(path, 'a'):
            os.utime(path, None)

    @classmethod
    def safe_delete(cls, path):
        if path and os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.isfile(path):
                # os.path.
                pass
            else:
                pass


class TestBundleCacheUsageBasicOperations(unittest2.TestCase):
    """
    Tests the basic database operations in a non-pipeline context:
        eg.: create table, an entry, update entry

    NOTE: we don't need to inherit from 'tanTestBase' for testing basic DB operations
    Actually
    """

    TMP_FOLDER_PREFIX = "TestBundleCacheUsageBasicOperations_"
    MAIN_TABLE_NAME = "bundles"
    TEST_BUNDLE_PATH1 = "some-bundle-path1"
    EXPECTED_DEFAULT_DB_FILENAME = "usage.db"
    PERF_TEST_ITERATION_COUNT = 100

    def setUp(self):
        # Actually we don't want to inherit from tanTestBase
        super(TestBundleCacheUsageBasicOperations, self).setUp()

        # TODO: cleanup when completed
        #self._temp_folder = tempfile.mkdtemp(prefix="TestBundleCacheUsageBasicOperations_")
        current_tmp_root = tempfile.tempdir
        self._temp_folder = os.path.join(tempfile.tempdir, TestBundleCacheUsageBasicOperations.TMP_FOLDER_PREFIX)
        if not os.path.exists(self._temp_folder):
            os.mkdir(self._temp_folder)

        #self._temp_folder = os.path.join("/", "Users", "nicolas-autodesk", "Library", "Caches", "Shotgun", "bundle_cache")

        self._expected_db_path = os.path.join(self._temp_folder,
                                              TestBundleCacheUsageBasicOperations.EXPECTED_DEFAULT_DB_FILENAME)

        # Preventively delete leftovers
        self.delete_db()

        self._db = BundleCacheUsage(self._temp_folder)

        if os.path.exists(self._expected_db_path):
            self._expected_db_path

    def tearDown(self):
        super(TestBundleCacheUsageBasicOperations, self).tearDown()
        self.delete_db()

    ###################################################################################################################
    #
    # Misc. Helper Methods
    #
    ###################################################################################################################

    @classmethod
    def _create_test_bundle_cache_structure(cls, root_folder):
        """
        Creates a bundle cache test struture containing 18 fake bundles.
        The structure also includes additional file for the purpose of verifying
        that the method walking down the path is able to limit it's search to
        bundle level folders.

        Additional `info.yml` might be found in the structure, they're from bundle plugins
        the tested code is expected to limit it's search to the bundle level.

        NOTE: The structure is generated dynamically rather than adding a yet a

        :param root_folder: A string path of the destination root folder
        """

        bundle_cache_root = os.path.join(root_folder, "bundle_cache")
        app_store_root = os.path.join(bundle_cache_root, "app_store")

        test_bundle_cache_structure = [
            os.path.join(app_store_root, "tk-multi-pythonconsole", "v1.1.1", "info.yml"),
            os.path.join(app_store_root, "tk-multi-launchapp", "v0.9.10", "info.yml"),
            os.path.join(app_store_root, "tk-multi-publish2", "v1.1.9", "info.yml"),
            os.path.join(app_store_root, "tk-shell", "v0.5.4", "info.yml"),
            os.path.join(app_store_root, "tk-framework-shotgunutils", "v5.2.3", "info.yml"),
            os.path.join(app_store_root, "tk-photoshopcc", "v1.1.7", "info.yml"),
            os.path.join(app_store_root, "tk-photoshopcc", "v1.1.7", "plugins", "basic", "info.yml"),
            os.path.join(app_store_root, "tk-framework-desktopserver", "v1.2.4", "info.yml"),
            os.path.join(app_store_root, "tk-framework-widget", "v0.2.6", "info.yml"),
            os.path.join(app_store_root, "tk-nuke", "v0.8.5", "info.yml"),
            os.path.join(app_store_root, "tk-nuke", "v0.8.5", "plugins", "basic", "info.yml"),
            os.path.join(app_store_root, "tk-multi-setframerange", "v0.3.0", "info.yml"),
            os.path.join(app_store_root, "tk-3dsmaxplus", "v0.4.1", "info.yml"),
            os.path.join(app_store_root, "tk-3dsmaxplus", "v0.4.1", "plugins", "basic", "info.yml"),
            os.path.join(app_store_root, "tk-multi-shotgunpanel", "v1.4.8", "info.yml"),
            os.path.join(app_store_root, "tk-maya", "v0.8.3", "info.yml"),
            os.path.join(app_store_root, "tk-maya", "v0.8.3", "plugins", "basic", "info.yml"),
            os.path.join(app_store_root, "tk-houdini", "v1.2.7", "info.yml"),
            os.path.join(app_store_root, "tk-houdini", "v1.2.7", "plugins", "test", "info.yml"),
            os.path.join(app_store_root, "tk-houdini", "v1.2.7", "plugins", "basic", "info.yml"),
            os.path.join(app_store_root, "tk-flame", "v1.9.6", "info.yml"),
            os.path.join(app_store_root, "tk-shotgun", "v0.6.0", "info.yml"),
            os.path.join(app_store_root, "tk-framework-qtwidgets", "v2.6.5", "info.yml"),
            os.path.join(app_store_root, "tk-multi-loader2", "v1.18.0", "info.yml")
        ]

        for item in test_bundle_cache_structure:
            Utils.touch(item)

    @property
    def db_exists(self):
        return os.path.exists(self._expected_db_path)

    @property
    def db_path(self):
        return self._expected_db_path

    def delete_db(self):
        if self.db_exists:
            os.remove(self.db_path)

    @property
    def db(self):
        if self._db:
            return self._db

        raise Exception("The test database is null, was it created?")

    @property
    def bundle_cache_root(self):
        return self._temp_folder

    @property
    def expected_db_path(self):
        return self._expected_db_path

    def _get_row_count(self, db, table_name=MAIN_TABLE_NAME):
        """
        Helper method returning the number of row in the specified table
        :param table_name: An optional string of the table name (default to main table)
        :return: An integer or -1 if cursor was not initialized
        """
        result = db._execute("SELECT * FROM %s" % (table_name))
        if result:
            rows = result.fetchall()
            return len(rows)
        else:
            return 0

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
        db = BundleCacheUsage(self._temp_folder)
        self.assertIsNotNone(db)
        self.assertIsInstance(db, BundleCacheUsage, "Was expecting class type to be BundleCacheUsage")

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
        Tests that a main table called 'bundles' gets created

        NOTE: Database connection and initials setup is done in the setUp method
        """
        ret = self.db._execute("SELECT name FROM main.sqlite_master WHERE type='table';")
        table_names = [x[0] for x in ret.fetchall()]
        self.assertEquals(len(table_names), 1, "Was expecting a single table to be created")
        self.assertEquals(table_names[0], "bundles", "Was expecting the main table to be called 'bundles'")

    def test_db_log_usage_basic(self):
        """
        Tests the logging basic usage is exception free

        NOTE: Database connection and initials setup is done in the setUp method
        """

        # Log some usage
        self.db.log_usage(TestBundleCacheUsageBasicOperations.TEST_BUNDLE_PATH1)

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

    def test_db_log_usage_for_new_entry(self):
        """
        Tests the basic of logging an entry not already existing in the database

        NOTE: Database connection and initials setup is done in the setUp method
        """

        BUNDLE_NAME = TestBundleCacheUsageBasicOperations.TEST_BUNDLE_PATH1

        # Low level test for record count
        self.assertEquals(self._get_row_count(self.db), 0, "Was not expecting any rows in main table just yet.")

        # Test before logging any usage
        self.assertEquals(self.db.get_usage_count(BUNDLE_NAME), 0,
                          "Was expecting a usage count of zero since we've just added a new entry"
        )

        # Log some usage
        self.db.log_usage(BUNDLE_NAME)

        # Low level test for record count
        self.assertEquals(self._get_row_count(self.db), 1, "Was now expecting one row since we've just logged an entry.")

        # Test after logging usage
        #self.db.get_last_usage_date(BUNDLE_NAME)
        self.assertEquals(self.db.get_usage_count(BUNDLE_NAME), 1,
                          "Was expecting a usage count of one since we've just logged usage")

    def test_db_log_usage_for_existing_entry(self):
        """
        Tests logging an existing entry

        NOTE: Database connection and initials setup is done in the setUp method
        """

        BUNDLE_NAME = TestBundleCacheUsageBasicOperations.TEST_BUNDLE_PATH1

        # Log some initial usage
        self.db.log_usage(BUNDLE_NAME)

        # Log again
        self.db.log_usage(BUNDLE_NAME)
        # ... and again
        self.db.log_usage(BUNDLE_NAME)

        # Low level test for record count, we're logging the same bundle name twice
        # We expect a single record still
        self.assertEquals(self._get_row_count(self.db), 1, "Was expecting a single row since we've logged the same entry.")

        # Test after logging usage
        self.assertEquals(self.db.get_usage_count(BUNDLE_NAME), 3,
                          "Was expecting a usage count of 2 since we've logged usage twice for same entry")

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
        self.db.commit()

        # Low level test for record count, we're logging the same bundle name twice
        # We expect a single record still
        self.assertEquals(self._get_row_count(self.db), 5, "Was expecting a single row since we've logged the same entry.")

    def _helper_test_db_read_and_update_performance(self, path, iteration_count = PERF_TEST_ITERATION_COUNT):
        """

        :return:
        """

        loop_count = 0

        start_time = time.time()
        db = BundleCacheUsage(path)
        while loop_count<iteration_count:
            bundle_test_name = "bundle-test-%03d" % (random.randint(0, 100))
            db.log_usage(bundle_test_name)
            db.commit()
            loop_count += 1

        db.close()
        elapsed = time.time() - start_time
        print("\nelapsed: %s" % (str(elapsed)))
        print("time per iteration: %s" % (str(elapsed/iteration_count)))

    def test_db_read_and_update_performance_file(self):
        self._helper_test_db_read_and_update_performance(self._temp_folder)

    def test_db_read_and_update_performance_memory(self):
        self._helper_test_db_read_and_update_performance(":memory:")

    def test_db_read_and_update_performance(self):
        """

        :return:
        """

        ITERATION_COUNT = TestBundleCacheUsageBasicOperations.PERF_TEST_ITERATION_COUNT
        iteration_count = 0

        start_time = time.time()
        while iteration_count<ITERATION_COUNT:
            db = BundleCacheUsage(self._temp_folder)
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

        db = BundleCacheUsage(self._temp_folder)
        start_time = time.time()
        while iteration_count<ITERATION_COUNT:
            #db = BundleCacheUsage(self._temp_folder)
            bundle_test_name = "bundle-test-%03d" % (random.randint(0, 100))
            #bundle_test_name = "bundle-test-%04d" % (iteration_count)
            db.log_usage(bundle_test_name)
            row_count = self._get_row_count(db)
            iteration_count += 1

        db.commit()
        db.close()

        elapsed = time.time() - start_time
        print("elapsed: %s" % (str(elapsed)))
        print("time per iteration: %s" % (str(elapsed/ITERATION_COUNT)))

    def test_walk_bundle_cache(self):
        """
        Tests & exercise the `_walk_bundle_cache` private method.
        The method is expected to find

        # The test structure created in the `_create_test_bundle_cache_structure`
        # See `_create_test_bundle_cache_structure`  documentation.

        """

        # Setup
        TestBundleCacheUsageBasicOperations._create_test_bundle_cache_structure(self.bundle_cache_root)

        # Tests using our test bundle cache test structure
        files = BundleCacheUsage._walk_bundle_cache(self.bundle_cache_root)
        self.assertEquals(len(files), 18)

        # Test with a non existing folder
        test_path = os.path.join(self.bundle_cache_root, "non-existing-folder")
        files = BundleCacheUsage._walk_bundle_cache(test_path)
        self.assertEquals(len(files), 0)

        # Try again, starting from a few level down. Although there are info.yml
        # files to be found they should not be recognized as bundles. Arbitrarly using
        # tk-maya  v0.8.3 since it includes extra info.yml file(s) found in plugin subfolder.
        test_path = os.path.join(self.bundle_cache_root, "bundle_cache", "app_store", "tk-maya")
        files = BundleCacheUsage._walk_bundle_cache(test_path)
        self.assertEquals(len(files), 0)
        test_path = os.path.join(self.bundle_cache_root, "bundle_cache", "app_store", "tk-maya", "v0.8.3")
        files = BundleCacheUsage._walk_bundle_cache(test_path)
        self.assertEquals(len(files), 0)
        test_path = os.path.join(self.bundle_cache_root, "bundle_cache", "app_store", "tk-maya", "v0.8.3", "plugins")
        files = BundleCacheUsage._walk_bundle_cache(test_path)
        self.assertEquals(len(files), 0)

        # Try again, starting a level up, the method should be able to find the app_store
        # folder and start from there.
        test_path = os.path.join(self.bundle_cache_root, os.pardir)
        files = BundleCacheUsage._walk_bundle_cache(test_path)
        self.assertEquals(len(files), 18)

        # Cleanup
        shutil.rmtree(self.bundle_cache_root)

    def test_scan_for_bundles(self):

        # Setup
        TestBundleCacheUsageBasicOperations._create_test_bundle_cache_structure(self.bundle_cache_root)

        # Cleanup
        shutil.rmtree(self.bundle_cache_root)
