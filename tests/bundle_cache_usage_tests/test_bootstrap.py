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

from tank_test.tank_test_base import TankTestBase, setUpModule, temp_env_var

import os
import sys
import time
import random
import unittest2
from mock import patch, Mock, MagicMock

import sgtk
from sgtk.bootstrap.manager import ToolkitManager
from sgtk.descriptor.bundle_cache_usage.manager import BundleCacheManager
from sgtk.pipelineconfig import PipelineConfiguration
from sgtk.util import LocalFileStorageManager

import tank

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

        self._saved_SHOTGUN_BUNDLE_CACHE_USAGE_NO_DELETE = \
            os.environ.get("SHOTGUN_BUNDLE_CACHE_USAGE_NO_DELETE", "")
        self._saved_SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE = \
            os.environ.get("SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE", "")

    def tearDown(self):
        os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_NO_DELETE"] = self._saved_SHOTGUN_BUNDLE_CACHE_USAGE_NO_DELETE
        os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE"] = self._saved_SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE
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
            os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_NO_DELETE"] = "1"
        else:
            os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_NO_DELETE"] = ""

        self._mock_default_user = MagicMock()

        self._patcher_get_default_user = patch(
            "tank.authentication.ShotgunAuthenticator.get_default_user",
            return_value=self._mock_default_user
        )
        self._patcher_get_default_user.start()
        self.addCleanup(self._patcher_get_default_user .stop)

        self.setup_fixtures(os.path.join("bootstrap_tests", "config"))
        self._my_pipeline_config = PipelineConfiguration(self.pipeline_config_root)

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

    def helper_test_cache_apps(self, no_delete=False, days_ago=0):

        if days_ago:
            # Override timestamp
            now = int(time.time())
            days_ago_timestamp = now - (days_ago * 24 * 3600)
            os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE"] = str(days_ago_timestamp)
            # Will setup a new database with bundle timestamp N days ago

        self.post_setup(no_delete)

        self.assertEquals(
            TestBundleCacheUsageBase.FAKE_TEST_BUNDLE_COUNT,
            self._bundle_cache_manager.get_bundle_count(),
            "Expecting all fake test bundles after test setup"
        )

        # Undo SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE so we get now timestamp
        os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE"] = ""

        # Actual tested statements
        self._toolkit_mgr._cache_apps(self._my_pipeline_config, "test_engine", None)

    @patch("tank.descriptor.io_descriptor.dev.IODescriptorDev.is_purgeable", return_value=True)
    def _test_process_bundle_cache_purge_no_old_bundles(self, is_purgeable_mock):
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
    def _test_process_bundle_cache_purge_with_old_bundles(self, is_purgeable_mock):
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
    def _test_process_bundle_cache_purge_with_old_bundles_with_no_delete(self, is_purgeable_mock):
        """
        Tests the ToolkitManager._process_bundle_cache_purge(...) method with old bundles AND
        the 'SHOTGUN_BUNDLE_CACHE_USAGE_NO_DELETE' environment variable active.

        The 'is_purgeable' mock allows forcing a bundle deletion of our Test-Dev descriptor
        """

        # 90 = mocking 90 days ago with 'SHOTGUN_BUNDLE_CACHE_USAGE_NO_DELETE' active
        self.helper_test_cache_apps(True, 90)

        self.assertEquals(TestBundleCacheUsageBase.FAKE_TEST_BUNDLE_COUNT,
                          self._bundle_cache_manager.get_bundle_count(),
                          "Was not expecting any bundles to be deleted."
        )


class TestBundleCacheUsageBootstraptPurge(TestBundleCacheUsageBase):

    def setUp(self):
        """
        The test class setup is somehow convoluted because of the import initialisation made,
        singleton nature of the BundleCacheManager class and override of the SHOTGUN_HOME
        which have to be before the earliest sgtk import made in the run_test.py startup script.

        We'll be forcing unloading of some import to assert that a db is indeed created
        overriding the bundle cache root default path.
        """
        super(TestBundleCacheUsageBootstraptPurge, self).setUp()

        self._saved_SHOTGUN_BUNDLE_CACHE_USAGE_NO_DELETE = \
            os.environ.get("SHOTGUN_BUNDLE_CACHE_USAGE_NO_DELETE", "")
        self._saved_SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE = \
            os.environ.get("SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE", "")

        self._setup_test_toolkit_manager()

    def tearDown(self):
        os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_NO_DELETE"] = self._saved_SHOTGUN_BUNDLE_CACHE_USAGE_NO_DELETE
        os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE"] = self._saved_SHOTGUN_BUNDLE_CACHE_USAGE_TIMESTAMP_OVERRIDE
        super(TestBundleCacheUsageBootstraptPurge, self).tearDown()

    def _setup_test_config(self):

        self.install_root = os.path.join(
            self.tk.pipeline_configuration.get_install_location(),
            "install"
        )

        self._patcher_get_default_user = patch(
            "tank.authentication.ShotgunAuthenticator.get_default_user",
            return_value=MagicMock()
        )
        self._patcher_get_default_user.start()
        self.addCleanup(self._patcher_get_default_user .stop)

        # set up bundle cache mock
        path = os.path.join(self.install_root, "app_store", "tk-config-test", "v0.1.2")
        self._create_info_yaml(path)

        self.config_1 = {"type": "app_store", "version": "v0.1.2", "name": "tk-config-test"}

        self._john_smith = self.mockgun.create("HumanUser", {"login": "john.smith", "name": "John Smith"})
        self._project = self.mockgun.create("Project", {"name": "my_project"})

        # set up a resolver
        self.resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="foo.maya",
            project_id=self._project["id"],
            bundle_cache_fallback_paths=[self.install_root]
        )

        self._create_pc(
            "Primary", self._project, plugin_ids="foo.*, bar, baz",
            descriptor="sgtk:descriptor:app_store?version=v0.1.2&name=tk-config-test"
        )

        config = self.resolver.resolve_shotgun_configuration(
            pipeline_config_identifier=None,
            fallback_config_descriptor=self.config_1,
            sg_connection=self.tk.shotgun,
            current_login="john.smith"
        )
        # TODO: how to fix this below ?
        config._path.current_os=self.pipeline_config_root
        config._path.macosx = self.pipeline_config_root

        return config

    def _setup_test_toolkit_manager(self):
        config = self._setup_test_config()

        # We mock '_get_updated_configuration' because we don't need to
        # go that deep into core. We just need 'some' configuration to allow
        # execution of the bundle cache usage code through `_bootstrap_sgtk`
        self._patcher_resolver = patch(
            "tank.bootstrap.manager.ToolkitManager._get_updated_configuration",
            return_value = config
        )
        self._patcher_resolver.start()
        self.addCleanup(self._patcher_resolver.stop)

        # We mock 'CoreImportHandler.swap_core' because, again, we definitively
        # don't to go that far for this particular test class.
        self._patcher_swap_core = patch(
            "tank.bootstrap.import_handler.CoreImportHandler.swap_core",
            return_value=None
        )
        self._patcher_swap_core.start()
        self.addCleanup(self._patcher_swap_core.stop)

        self._toolkit_mgr = ToolkitManager()
        self._toolkit_mgr.caching_policy = ToolkitManager.CACHE_FULL

    def _create_info_yaml(self, path):
        """
        create a mock info.yml
        """
        sgtk.util.filesystem.ensure_folder_exists(path)
        fh = open(os.path.join(path, "info.yml"), "wt")
        fh.write("foo")
        fh.close()

    def _create_pc(self, code, project=None, path=None, users=[], plugin_ids=None, descriptor=None):
        """
        Creates a pipeline configuration.

        :param code: Name of the pipeline configuration.
        :param project: Project of the pipeline configuration.
        :param path: mac_path, windows_path and linux_path will be set to this.
        :param users: List of users who should be able to use this pipeline.
        :param plugin_ids: Plugin ids for the pipeline configuration.
        :param descriptor: Descriptor for the pipeline configuration

        :returns: Dictionary with keys entity_type and entity_id.
        """

        return self.mockgun.create(
            "PipelineConfiguration", dict(
                code=code,
                project=project,
                users=users,
                windows_path=path,
                mac_path=path,
                linux_path=path,
                plugin_ids=plugin_ids,
                descriptor=descriptor
            )
        )

    def test_bundle_cache_usage_database_created_and_populated(self):
        """
        Tests that the bundle cache usage database gets created and populatedt
        after a call to the `ToolkitManager._bootstrap_sgtk` method.
        """

        # Force single release and database file deletion
        # that is created by creating PipelineConfig
        BundleCacheManager.delete_instance()
        if os.path.exists(self._expected_db_path):
            os.remove(self._expected_db_path)

        # Assert that TookKitManager import and setup caused creation of the database file
        self.assertFalse(os.path.exists(self._expected_db_path))
        self._toolkit_mgr._bootstrap_sgtk("test_engine", None)
        self.assertTrue(os.path.exists(self._expected_db_path))

        # Create a temporary instance, for querying database
        # state and content. We can supply a None parameter
        # since an instance already exists.
        bundle_cache_usage_mgr = BundleCacheManager(None)
        self.assertTrue(
            bundle_cache_usage_mgr.initial_populate_performed,
            "Was expecting database initial population done."
        )
        self.assertEquals(
            TestBundleCacheUsageBase.FAKE_TEST_BUNDLE_COUNT,
            bundle_cache_usage_mgr.get_bundle_count(),
            "Was expecting database to be initially populated with all fake test bundles"
        )












