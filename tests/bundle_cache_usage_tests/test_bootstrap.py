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

        self._saved_TK_BUNDLE_USAGE_TRACKING_DISABLE = os.environ.get('TK_BUNDLE_USAGE_TRACKING_DISABLE', "")
        self._saved_TK_BUNDLE_USAGE_TRACKING_NO_DELETE = os.environ.get('TK_BUNDLE_USAGE_TRACKING_NO_DELETE', "")

    def tearDown(self):
        os.environ["TK_BUNDLE_USAGE_TRACKING_DISABLE"] = self._saved_TK_BUNDLE_USAGE_TRACKING_DISABLE
        os.environ["TK_BUNDLE_USAGE_TRACKING_NO_DELETE"] = self._saved_TK_BUNDLE_USAGE_TRACKING_NO_DELETE
        super(TestBundleCacheUsageIndirect, self).tearDown()

    @classmethod
    def _mocked_report_progress(*args, **kwargs):
        # TODO: verify what goes through here
        if len(args) >= 4:
            pct = int(args[2] * 100)
            msg = args[3]
            #print("Progress: %s --- %s" % (str(pct), msg))

    def post_setup(self, no_delete=False):

        if no_delete:
            os.environ["TK_BUNDLE_USAGE_TRACKING_NO_DELETE"] = "1"
        else:
            os.environ["TK_BUNDLE_USAGE_TRACKING_NO_DELETE"] = ""

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

        self._patcher_report_progress = patch(
            "tank.bootstrap.manager.ToolkitManager._report_progress",
            TestBundleCacheUsageIndirect._mocked_report_progress
        )
        self._patcher_report_progress.start()
        self.addCleanup(self._patcher_report_progress .stop)

    def test_bundle_cache_database_created(self):
        """
        Test that the bundle cache usage database gets created after importing base modules.
        """
        self.post_setup()
        # Assert that TookKitManager import and setup caused creation of the database file
        self.assertTrue(os.path.exists(self._expected_db_path))
        self.assertEquals(
            TestBundleCacheUsageBase.FAKE_TEST_BUNDLE_COUNT,
            self._bundle_cache_manager.get_bundle_count(),
            "Was expecting database to be initially populated with all fake test bundles"
        )

    def helper_test_cache_apps(self, no_delete=False, days_ago=0):

        self.post_setup(no_delete)

        self.assertEquals(
            TestBundleCacheUsageBase.FAKE_TEST_BUNDLE_COUNT,
            self._bundle_cache_manager.get_bundle_count(),
            "Expecting all fake test bundles after test setup"
        )

        # Mock `time.time` so we can hit (through usage of the `_cache_apps` below )
        # test bundles with an old timestamp.
        if days_ago:
            now = int(time.time())
            days_ago_timestamp = now - (days_ago * 24 * 3600)
            with patch("time.time") as mocked_time_time:
                mocked_time_time.return_value = days_ago_timestamp
                # Test mocking itself
                self.assertEquals(days_ago_timestamp, int(time.time()))
                # Actual tested statements with a time.time mock
                self._toolkit_mgr._cache_apps(self._my_pipeline_config, "test_engine", None)
        else:
            # Actual tested statements without a time.time mock
            self._toolkit_mgr._cache_apps(self._my_pipeline_config, "test_engine", None)

    @patch("tank.descriptor.io_descriptor.dev.IODescriptorDev.is_purgeable", return_value=True)
    def test_process_bundle_cache_purge_no_old_bundles(self, is_purgeable_mock):
        """
        Tests the ToolkitManager._cache_apps(...) and method.

        The 'is_purgeable' mock allows forcing a bundle deletion of our Test-Dev descriptor
        """

        # 0 = not mocking days ago
        self.helper_test_cache_apps(False, 0)

        self.assertEquals(TestBundleCacheUsageBase.FAKE_TEST_BUNDLE_COUNT,
                          self._bundle_cache_manager.get_bundle_count(),
                          "Not expecting anything to be deleted since no bundle is old"
        )

    @patch("tank.descriptor.io_descriptor.dev.IODescriptorDev.is_purgeable", return_value=True)
    def test_process_bundle_cache_purge_with_old_bundles(self, is_purgeable_mock):
        """
        Tests the ToolkitManager._process_bundle_cache_purge(...) method with old bundles.

        The 'is_purgeable' mock allows forcing a bundle deletion of our Test-Dev descriptor
        """

        # 90 = mocking 90 days ago
        self.helper_test_cache_apps(False, 90)

        self.assertEquals(0,
                          self._bundle_cache_manager.get_bundle_count(),
                          "Was expecting all bundles to be deleted."
        )

    @patch("tank.descriptor.io_descriptor.dev.IODescriptorDev.is_purgeable", return_value=True)
    def test_process_bundle_cache_purge_with_old_bundles_with_no_delete(self, is_purgeable_mock):
        """
        Tests the ToolkitManager._process_bundle_cache_purge(...) method with old bundles AND
        the 'TK_BUNDLE_USAGE_TRACKING_NO_DELETE' environment variable active.

        The 'is_purgeable' mock allows forcing a bundle deletion of our Test-Dev descriptor
        """

        # 90 = mocking 90 days ago with 'TK_BUNDLE_USAGE_TRACKING_NO_DELETE' active
        self.helper_test_cache_apps(True, 90)

        self.assertEquals(TestBundleCacheUsageBase.FAKE_TEST_BUNDLE_COUNT,
                          self._bundle_cache_manager.get_bundle_count(),
                          "Was not expecting any bundles to be deleted."
        )







