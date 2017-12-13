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
import sys
import time
import random
import unittest2
from mock import patch, Mock, MagicMock

from sgtk.descriptor.bundle_cache_usage.manager import BundleCacheManager
from sgtk.pipelineconfig import PipelineConfiguration
from sgtk.util import LocalFileStorageManager

from .test_base import TestBundleCacheUsageBase, Utils

class TestBundleCacheUsageIndirect(TestBundleCacheUsageBase):

    """
    Test bundle cache usage indirecvtly through bootstrap related calls.
    """

    def setUp(self):
        """
        The test class setup is somehow convoluted because of the import initialisation made,
        singleton nature of the BundleCacheManager class and override of the SHOTGUN_HOME
        which have to be before the earliest sgtk import made in the run_test.py startup script.

        We'll be forcing unloading of some import to assert that a db is indeed created
        overriding the bundle cache root default path.
        """
        super(TestBundleCacheUsageIndirect, self).setUp()

        self._mock_default_user = MagicMock()

        self._patcher_get_default_user = patch(
            "tank.authentication.ShotgunAuthenticator.get_default_user",
            return_value=self._mock_default_user
        )
        self._patcher_get_default_user.start()
        self.addCleanup(self._patcher_get_default_user .stop)

        self.setup_fixtures(os.path.join("bootstrap_tests", "config"))
        self._my_pipeline_config = PipelineConfiguration(self.pipeline_config_root)

        # We want to force re-importing of the 'bootstrap.manager'
        # and 'bundle_cache_usage' modules. So we have control over
        # the bundle_cache_root path used.
        delete_modules = [
            "sgtk.bootstrap.manager",
            "tank.bootstrap.manager",
            "sgtk.descriptor.bundle_cache_usage",
            "tank.descriptor.bundle_cache_usage"
        ]
        for module in delete_modules:
            try:
                del sys.modules[module]
            except:
                pass

        import sgtk.bootstrap.manager
        from sgtk.bootstrap.manager import ToolkitManager

        self._toolkit_mgr = ToolkitManager()
        self._toolkit_mgr.caching_policy = ToolkitManager.CACHE_FULL

        bundle_cache_root = os.path.join(
            LocalFileStorageManager.get_global_root(LocalFileStorageManager.CACHE),
            "bundle_cache"
        )
        self._bundle_cache_manager = BundleCacheManager(bundle_cache_root)

    @classmethod
    def _mocked_report_progress(*args, **kwargs):
        # TODO: verify what goes through here
        if len(args) >= 4:
            pct = int(args[2] * 100)
            msg = args[3]
            #print("Progress: %s --- %s" % (str(pct), msg))

    def test_bundle_cache_database_created(self):
        """
        Test that the bundle cache usage database gets created after importing base modules.
        """

        # Assert that TookKitManager import and setup caused creation of the database file
        self.assertTrue(os.path.exists(self._expected_db_path))

    def helper_test_cache_apps(self, disable_bundle_cache_usage):

        if disable_bundle_cache_usage:
            os.environ["TK_DISABLE_BUNDLE_TRACKING"] = "1"
        else:
            os.environ["TK_DISABLE_BUNDLE_TRACKING"] = ""

        # Test that we get zero before an initial call to '_cache_apps' is made
        start_time = time.time()
        self.assertEquals(0, self._bundle_cache_manager.get_bundle_count())
        self.assertLess(time.time() - start_time, 0.25, "Was worker stopped?")

        # Actual tested statements
        start_time = time.time()
        self._toolkit_mgr._cache_apps(self._my_pipeline_config, "test_engine", None)
        expected_wait_time = 0.25 if disable_bundle_cache_usage else 1.0
        self.assertLess(time.time() - start_time, expected_wait_time, "Unexpected long execution time")

        expected_bundle_count = 0 if disable_bundle_cache_usage else TestBundleCacheUsageBase.FAKE_TEST_BUNDLE_COUNT
        start_time = time.time()
        self.assertEquals(expected_bundle_count, self._bundle_cache_manager.get_bundle_count())
        self.assertLess(time.time() - start_time, 1.0, "Unexpected long execution time")

    @patch("tank.bootstrap.manager.ToolkitManager._report_progress", _mocked_report_progress)
    def test_bundle_cache_usage_initial_db_population(self):
        """
        Tests initial creation of the bundle cache usage database
        WITH and without the 'TK_DISABLE_BUNDLE_TRACKING' defined.

        The test is performed indirectly through usage of the `ToolkitManager._cache_apps(...)` method.
        """
        self.helper_test_cache_apps(disable_bundle_cache_usage=True)
        self.helper_test_cache_apps(disable_bundle_cache_usage=False)

    @patch("tank.bootstrap.manager.ToolkitManager._report_progress", _mocked_report_progress)
    @patch("tank.descriptor.io_descriptor.dev.IODescriptorDev.is_purgeable", return_value=True)
    def _test_cache_apps(self, jjj2):
        """
        Tests the ToolkitManager._cache_apps(...) and method.

        The 'is_purgeable' mock allows us forcing a bundle deletion our Test-Dev descriptor
        """

        #patcher = patch_app_store()
        #self._mock_store = patcher.start()
        #self.addCleanup(patcher.stop)

        # TODO: Is this any useful??? Can it serve similar purpose to
        # my own method for creating a fake test bundle cache?
        self.setup_fixtures(os.path.join("bootstrap_tests", "config"))
        self._mock_store.add_framework("test_framework", "v2.1.0")

        # Setup
        pc = PipelineConfiguration(self.pipeline_config_root)
        modified_mgr = ToolkitManager()
        modified_mgr.caching_policy = ToolkitManager.CACHE_FULL

        # Mock `time.time` so we can hit (through usage of the `_cache_apps` below )
        # test bundles with an old timestamp.
        now = int(time.time())
        ninety_days_ago = now - (90 * 24 * 3600)

        with patch("time.time") as mocked_time_time:
            mocked_time_time.return_value = ninety_days_ago
            # Hit some bundles!
            modified_mgr._cache_apps(pc, "test_engine", None)

    @patch("tank.bootstrap.manager.ToolkitManager._report_progress", _mocked_report_progress)
    @patch("tank.descriptor.io_descriptor.dev.IODescriptorDev.is_purgeable", return_value=True)
    def _test_process_bundle_cache_purge(self, jjj2):
        """
        Tests the ToolkitManager._cache_apps(...) and method.

        The
        """
        from tank_test.mock_appstore import TankMockStoreDescriptor, patch_app_store

        patcher = patch_app_store()
        self._mock_store = patcher.start()
        self.addCleanup(patcher.stop)

        # TODO: Is this any useful??? Can it serve similar purpose to
        # my own method for creating a fake test bundle cache?
        self.setup_fixtures(os.path.join("bootstrap_tests", "config"))
        self._mock_store.add_framework("test_framework", "v2.1.0")

        from sgtk.pipelineconfig import PipelineConfiguration

        pc = PipelineConfiguration(self.pipeline_config_root)
        # pc = PipelineConfiguration(os.path.join(self.fixtures_root, "bootstrap_tests"))

        modified_mgr = ToolkitManager()
        modified_mgr.caching_policy = ToolkitManager.CACHE_FULL
        modified_mgr._cache_apps(pc, "test_engine", None)




