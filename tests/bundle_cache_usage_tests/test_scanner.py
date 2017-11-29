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
import unittest2

from .test_base import TestBundleCacheUsageBase, Utils

from sgtk.descriptor.bundle_cache_usage.scanner import BundleCacheScanner
from sgtk.descriptor.bundle_cache_usage.writer import BundleCacheUsageWriter

class TestBundleCacheScanner(TestBundleCacheUsageBase):
    """
    Test walking the bundle cache searching or discovering bundles in the app_store
    """

    # The number of bundles in the test bundle cache
    EXPECTED_BUNDLE_COUNT = 18

    def setUp(self):
        super(TestBundleCacheScanner, self).setUp()

       # TODO: How do you get bundle_cache test path as opposed to what is returned by
        # LocalFileStorageManager.get_global_root(LocalFileStorageManager.CACHE)
        os.environ["SHOTGUN_HOME"] = self.bundle_cache_root

    def tearDown(self):
        Utils.safe_delete(self.bundle_cache_root)
        super(TestBundleCacheScanner, self).tearDown()

    def test_walk_bundle_cache(self):
        """
        Tests & exercise the `_walk_bundle_cache` private method.
        The method is expected to find

        # The test structure created in the `_create_test_bundle_cache_structure`
        # See `_create_test_bundle_cache_structure`  documentation.

        """
        # Tests using our test bundle cache test structure
        files = BundleCacheScanner.find_bundles(self.bundle_cache_root)
        self.assertEquals(len(files), TestBundleCacheScanner.EXPECTED_BUNDLE_COUNT)

    def test_walk_bundle_cache_non_existing_folder(self):
        """
        Test with a non existing folder
        """
        test_path = os.path.join(self.bundle_cache_root, "non-existing-folder")
        files = BundleCacheScanner.find_bundles(test_path)
        self.assertEquals(len(files), 0)

    def _test_walk_bundle_cache_level_down(self):
        # TODO: requires some result update
        #
        # Try again, starting from a few level down. Although there are info.yml
        # files to be found they should not be recognized as bundles. Arbitrarly using
        # tk-maya  v0.8.3 since it includes extra info.yml file(s) found in plugin subfolder.
        test_path = os.path.join(self.bundle_cache_root, "app_store", "tk-maya")
        files = BundleCacheScanner.find_bundles(test_path)
        self.assertEquals(len(files), )
        test_path = os.path.join(self.bundle_cache_root, "app_store", "tk-maya", "v0.8.3")
        files = BundleCacheScanner.find_bundles(test_path)
        self.assertEquals(len(files), 0)
        test_path = os.path.join(self.bundle_cache_root, "app_store", "tk-maya", "v0.8.3", "plugins")
        files = BundleCacheScanner.find_bundles(test_path)
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
        files = BundleCacheScanner.find_bundles(test_path)
        self.assertEquals(len(files), TestBundleCacheScanner.EXPECTED_BUNDLE_COUNT)

