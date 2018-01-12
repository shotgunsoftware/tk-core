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
import datetime
import random

from tank.util.filesystem import safe_delete_folder
from sgtk.descriptor.bundle_cache_usage.database import BundleCacheUsageDatabase
from sgtk.descriptor.bundle_cache_usage.tracker import BundleCacheUsageTracker


class Utils(object):
    """
    A collection of miscellaneous non-specific methods
    used throughout this module.
    """

    # An excerpt from chapter of Jules Verne' TWENTY THOUSAND LEAGUES UNDER THE SEA
    # Ref: https://www.gutenberg.org/files/164/164-h/164-h.htm
    text_data = \
        "The year 1866 was signalised by a remarkable incident, a mysterious and" \
        "puzzling phenomenon, which doubtless no one has yet forgotten. Not to mention" \
        "rumours which agitated the maritime population and excited the public mind, "\
        " even in the interior of continents, seafaring men were particularly excited." \
        "Merchants, common sailors, captains of vessels, skippers, both of Europe and "\
        "America, naval officers of all countries, and the Governments of several States "\
        "on the two continents, were deeply interested in the matter."

    @classmethod
    def touch(cls, path):
        """
        Simply 'touch' the specified file

        Reference:
        https://stackoverflow.com/a/12654798/710183

        :param path: a str full path and filename to a file we want to create/touch
        """
        dirs = os.path.dirname(path)

        if not os.path.exists(dirs):
            os.makedirs(dirs)

        with open(path, 'a'):
            os.utime(path, None)

    @classmethod
    def write_bogus_data(cls, path):
        """
        Writes bogus test data to the specified file.

        :param path: a str full path and file to write bogus data to.
        """
        full_length = len(Utils.text_data)
        quater_length = full_length / 4
        random_length = random.randrange(quater_length, full_length)

        data_to_write = Utils.text_data[:random_length]

        dirs = os.path.dirname(path)

        if not os.path.exists(dirs):
            os.makedirs(dirs)

        with open(path, 'w') as f:
            f.write(data_to_write)


class TestBundleCacheUsageBase(TankTestBase):
    """
    TestBundleCacheUsageBase test base class
    """
    EXPECTED_DEFAULT_DB_FILENAME = "bundle_usage.sqlite3"

    # The number of bundles in the test bundle cache
    FAKE_TEST_BUNDLE_COUNT = 18 # as created in `_create_test_app_store_cache`
    FAKE_TEST_BUNDLE_FILE_COUNT = 75  # as created in `_create_test_app_store_cache`
    DEBUG = False

    WAIT_TIME_INSTANT = 0.25
    WAIT_TIME_SHORT = 1.0
    WAIT_TIME_MEDIUM = 5.0
    WAIT_TIME_LONG = 10.0
    WAIT_TIME_MEGA_LONG = 120.0
    DEFAULT_LOOP_COUNT = 1000

    WORKER_PROCESSING_TIME = WAIT_TIME_INSTANT

    def setUp(self):
        super(TestBundleCacheUsageBase, self).setUp()

        self._expected_db_path = os.path.join(self.bundle_cache_root, BundleCacheUsageDatabase.DB_FILENAME)
        self._create_test_bundle_cache()
        self._test_bundle_path = os.path.join(self.app_store_root, "tk-shell", "v0.5.6")

        self._saved_SHOTGUN_BUNDLE_CACHE_USAGE_NO_DELETE = \
            os.environ.get("SHOTGUN_BUNDLE_CACHE_USAGE_NO_DELETE", "")

        self._saved_SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE = \
            os.environ.get("SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE", "")

        self._now = time.time()
        self._expected_date_format = "%A %d %B %Y %H:%M:%S"

        # Bundle date when added to the database
        self._bundle_creation_time = int(self._now) - (90 * 24 * 3600)
        self._bundle_creation_date_formatted = datetime.datetime.fromtimestamp(
            self._bundle_creation_time
        ).strftime(self._expected_date_format)

        # Bundle last usage date
        self._bundle_last_usage_time = int(self._now) - (65 * 24 * 3600)
        self._bundle_last_usage_date_formatted = datetime.datetime.fromtimestamp(
            self._bundle_last_usage_time
        ).strftime(self._expected_date_format)

        self._dev_bundle_path = self.create_dev_test_bundle(self.bundle_cache_root)

    def tearDown(self):
        os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_NO_DELETE"] = \
            self._saved_SHOTGUN_BUNDLE_CACHE_USAGE_NO_DELETE

        os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE"] = \
            self._saved_SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE

        BundleCacheUsageTracker.delete_instance()
        self.delete_db()
        safe_delete_folder(self._dev_bundle_path)
        super(TestBundleCacheUsageBase, self).tearDown()

    def assertIsWithinPct(self, test_value, expected_value, tolerance):
        """
        Custom assert method for testing that a value is within tolerance.

        :param test_value: A float value to check
        :param expected_value:  A float value of what is expected
        :param tolerance: A float tolerance expressed in percentage [0.0, 100.0]
        """
        expected_value_pct = expected_value * tolerance / 100.0
        min_value = expected_value - expected_value_pct
        max_value = expected_value + expected_value_pct

        self.assertGreaterEqual(test_value, min_value)
        self.assertLessEqual(test_value, max_value)

    @property
    def app_store_root(self):
        return os.path.join(self.bundle_cache_root, "app_store")

    @property
    def bundle_cache_root(self):
        return os.path.join(self.tank_temp, "bundle_cache")

    def _create_test_bundle_cache(self):
        """
        Creates a bundle cache test struture containing 18 fake bundles.
        The structure also includes additional file for the purpose of verifying
        that the method walking down the path is able to limit it's search to
        bundle level folders.

        Additional `info.yml` might be found in the structure, they're from bundle plugins
        the tested code is expected to limit it's search to the bundle level.

        NOTE: The structure is generated dynamically rather than adding a yet a
        """
        if not os.path.exists(self.bundle_cache_root):
            os.makedirs(self.bundle_cache_root)

        TestBundleCacheUsageBase._create_test_app_store_cache(self.bundle_cache_root)

    def _get_app_store_file_list(self):
        """
        Returns the list of file created in our fake/test bundle_cache/app_store folder
        :return: a list of paths
        """
        app_store_file_list = []
        for (dirpath, dirnames, filenames) in os.walk(self.app_store_root):
            app_store_file_list.append(dirpath)
            for filename in filenames:
                fullpath = os.path.join(dirpath, filename)
                app_store_file_list.append(fullpath)

        return app_store_file_list

    @classmethod
    def _create_test_app_store_cache(cls, bundle_cache_root):
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
        app_store_root = os.path.join(bundle_cache_root, "app_store")

        test_bundle_cache_structure = [
            os.path.join(app_store_root, "tk-multi-pythonconsole", "v1.1.1", "info.yml"),
            os.path.join(app_store_root, "tk-multi-launchapp", "v0.9.10", "info.yml"),
            os.path.join(app_store_root, "tk-shell", "v0.5.4", "info.yml"),
            os.path.join(app_store_root, "tk-shell", "v0.5.6", "info.yml"),
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
            os.path.join(app_store_root, "tk-maya", "v0.8.3", "some_file.txt"),
            os.path.join(app_store_root, "tk-maya", "v0.8.3", "another_file.txt"),
            os.path.join(app_store_root, "tk-maya", "v0.8.3", "plugins", "basic", "info.yml"),
            os.path.join(app_store_root, "tk-maya", "v0.8.3", "plugins", "basic", "some_file.txt"),
            os.path.join(app_store_root, "tk-maya", "v0.8.3", "plugins", "basic", "another_file.txt"),
            os.path.join(app_store_root, "tk-houdini", "v1.2.7", "info.yml"),
            os.path.join(app_store_root, "tk-houdini", "v1.2.7", "plugins", "test", "info.yml"),
            os.path.join(app_store_root, "tk-houdini", "v1.2.7", "plugins", "basic", "info.yml"),
            os.path.join(app_store_root, "tk-flame", "v1.9.6", "info.yml"),
            os.path.join(app_store_root, "tk-shotgun", "v0.6.0", "info.yml"),
            os.path.join(app_store_root, "tk-framework-qtwidgets", "v2.6.5", "info.yml"),
            os.path.join(app_store_root, "tk-multi-loader2", "v1.18.0", "info.yml")
        ]

        for item in test_bundle_cache_structure:
            Utils.write_bogus_data(item)

    @classmethod
    def create_dev_test_bundle(cls, bundle_cache_root):
        """
        Creates a test tk-maya dev bundle outside of the app store / bundle cache

        :param bundle_cache_root: A string path of the used bundle cache root folder
        :return: A str dev bundle path
        """

        bundle_cache_parent_dir = os.path.abspath(os.path.join(bundle_cache_root, os.pardir))
        tk_maya_dev_bundle_path = os.path.join(bundle_cache_parent_dir, "dev", "tk-maya")
        os.makedirs(tk_maya_dev_bundle_path)

        test_bundle_cache_structure = [
            os.path.join(tk_maya_dev_bundle_path, "info.yml"),
            os.path.join(tk_maya_dev_bundle_path, "some_file.txt"),
            os.path.join(tk_maya_dev_bundle_path, "another_file.txt"),
            os.path.join(tk_maya_dev_bundle_path, "plugins", "basic", "info.yml"),
            os.path.join(tk_maya_dev_bundle_path, "plugins", "basic", "some_file.txt"),
            os.path.join(tk_maya_dev_bundle_path, "plugins", "basic", "another_file.txt")
        ]

        for item in test_bundle_cache_structure:
            Utils.write_bogus_data(item)

        return tk_maya_dev_bundle_path

    @classmethod
    def _get_test_bundles(self, bundle_cache_root):

        """
        Helper method returning the list of fake bundles created
        in the `_create_test_app_store_cache` method.
        :return: A list of paths
        """

        app_store_root = os.path.join(bundle_cache_root, "app_store")

        return [
            os.path.join(app_store_root, "tk-multi-pythonconsole", "v1.1.1"),
            os.path.join(app_store_root, "tk-multi-launchapp", "v0.9.10"),
            os.path.join(app_store_root, "tk-shell", "v0.5.4"),
            os.path.join(app_store_root, "tk-shell", "v0.5.6"),
            os.path.join(app_store_root, "tk-framework-shotgunutils", "v5.2.3"),
            os.path.join(app_store_root, "tk-photoshopcc", "v1.1.7"),
            os.path.join(app_store_root, "tk-framework-desktopserver", "v1.2.4"),
            os.path.join(app_store_root, "tk-framework-widget", "v0.2.6"),
            os.path.join(app_store_root, "tk-nuke", "v0.8.5"),
            os.path.join(app_store_root, "tk-multi-setframerange", "v0.3.0"),
            os.path.join(app_store_root, "tk-3dsmaxplus", "v0.4.1"),
            os.path.join(app_store_root, "tk-multi-shotgunpanel", "v1.4.8"),
            os.path.join(app_store_root, "tk-maya", "v0.8.3"),
            os.path.join(app_store_root, "tk-houdini", "v1.2.7"),
            os.path.join(app_store_root, "tk-flame", "v1.9.6"),
            os.path.join(app_store_root, "tk-shotgun", "v0.6.0"),
            os.path.join(app_store_root, "tk-framework-qtwidgets", "v2.6.5"),
            os.path.join(app_store_root, "tk-multi-loader2", "v1.18.0")
        ]

    ###################################################################################################################
    #
    # Misc. Helper Methods
    #
    ###################################################################################################################

    @property
    def db_exists(self):
        return os.path.exists(self._expected_db_path)

    @property
    def db_path(self):
        return self._expected_db_path

    def delete_db(self):
        if self.db_exists:
            BundleCacheUsageTracker.delete_instance(self.WAIT_TIME_MEGA_LONG)
            retry_count = 5
            while retry_count:
                try:
                    os.remove(self.db_path)
                    break
                except Exception as e:
                    retry_count -= 1
                    if retry_count > 0:
                        print("Error trying to delete the bundle cache usage tracking database, retrying...")
                    else:
                        print("Unexpected error trying to delete the bundle cache usage tracking database.\n"
                              "The file was probably not closed properly:\n%s" % (e))
                    time.sleep(1.0)

    @property
    def db(self):
        if self._db:
            return self._db

        raise Exception("The test database is null, was it created?")

    @property
    def expected_db_path(self):
        return self._expected_db_path
