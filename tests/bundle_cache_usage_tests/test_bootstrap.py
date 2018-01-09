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
from mock import patch, MagicMock

import sgtk
from sgtk.bootstrap.manager import ToolkitManager
from sgtk.descriptor.bundle_cache_usage.tracker import BundleCacheUsageTracker
from sgtk.descriptor.bundle_cache_usage.purger import BundleCacheUsagePurger
from sgtk.pipelineconfig import PipelineConfiguration
from sgtk.util import LocalFileStorageManager

from .test_base import TestBundleCacheUsageBase


class TestBundleCacheUsageIndirect(TestBundleCacheUsageBase):
    """
    Test bundle cache usage indirectly through bootstrap related calls.
    """

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
        self._bundle_cache_manager = BundleCacheUsagePurger(bundle_cache_root)


class TestBundleCacheUsageBootstraptPurge(TestBundleCacheUsageBase):

    def setUp(self):
        """
        The test class setup is somehow convoluted because of the import initialisation made,
        singleton nature of the BundleCacheUsagePurger class and override of the SHOTGUN_HOME
        which have to be before the earliest sgtk import made in the run_test.py startup script.

        We'll be forcing unloading of some import to assert that a db is indeed created
        overriding the bundle cache root default path.
        """
        super(TestBundleCacheUsageBootstraptPurge, self).setUp()
        self._setup_test_toolkit_manager()

    def tearDown(self):
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
        # TODO: NICOLAS: how to fix the hack below ?
        #       How to link both the resolved config
        #       and path where actual config exists?
        config._path.current_os = self.pipeline_config_root

        return config

    def _setup_test_toolkit_manager(self):
        config = self._setup_test_config()

        # We mock '_get_updated_configuration' because we don't need to
        # go that deep into core. We just need 'some' configuration to allow
        # execution of the bundle cache usage code through `_bootstrap_sgtk`
        self._patcher_resolver = patch(
            "tank.bootstrap.manager.ToolkitManager._get_updated_configuration",
            return_value=config
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

        # Test that the database will get created from a call to
        # '_bootstrap_sgtk' method.
        #
        # The database gets created from pipeline config being created.
        # For this test we do want to start without a db created
        self.delete_db()
        self.assertFalse(os.path.exists(self._expected_db_path))
        self._toolkit_mgr._bootstrap_sgtk("test_engine", None)
        self.assertTrue(os.path.exists(self._expected_db_path))

        # Create a temporary instance, for querying database
        # state and content. We can supply a None parameter
        # since an instance already exists.
        bundle_cache_usage_purger = BundleCacheUsagePurger()
        self.assertTrue(
            bundle_cache_usage_purger.initial_populate_performed,
            "Was expecting database initial population done."
        )
        self.assertEquals(
            TestBundleCacheUsageBase.FAKE_TEST_BUNDLE_COUNT,
            bundle_cache_usage_purger.bundle_count,
            "Was expecting database to be initially populated with all fake test bundles"
        )

    def helper_test_purge_bundles(self):
        """
        Helper method for bundle purge tests.

        Here is the summary of what the method does:

        - Create test app_store (actually done is setUp())
        - Verify that all file are present (actually done is setUp())
        - Back in time, database is populated with content of our
          test app_store (18 fake bundles with 2 versions of 'tk-shell')
        - Check database has 18 bundles.
        - In present time we log usage of 'tk-shell/v0.5.6'
        - Call `_bootstrap_sgtk` 
        - Expect almost everything to be deleted beside (tk-shell/v0.5.6)
        - Check database as only 1 bundle left.
        - Check that all bundles besire tk-shell/v0.5.6 are deleted.
        """

        # Trigger initial bundle creation in database some time ago
        with patch("time.time", return_value=self._bundle_creation_time):

            # Make an initial call to setup the database (in the past)
            self._toolkit_mgr._bootstrap_sgtk("test_engine", None)

        # Assert database state
        self.assertTrue(os.path.exists(self._expected_db_path))

        # NOW, we create a temporary instance, for querying database
        # state and content.
        bundle_cache_usage_purger = BundleCacheUsagePurger()
        self.assertTrue(
            bundle_cache_usage_purger.initial_populate_performed,
            "Was expecting database initial population done."
        )
        self.assertEquals(
            TestBundleCacheUsageBase.FAKE_TEST_BUNDLE_COUNT,
            bundle_cache_usage_purger.bundle_count,
            "Was expecting database to be initially populated with all fake test bundles"
        )

        #
        # IMPORTANT: This assumes that tracker init was done in 'PipelineConfig' class
        #
        BundleCacheUsageTracker.track_usage(self._test_bundle_path)
        time.sleep(self.WAIT_TIME_INSTANT) # allow worker some processing time

        # Verify that we receive all bundle minus the one we just logged some usage for
        bundle_list = bundle_cache_usage_purger.get_unused_bundles()
        self.assertEquals(
            TestBundleCacheUsageBase.FAKE_TEST_BUNDLE_COUNT - 1,
            len(bundle_list),
            "Was expecting to get all bundles but one (the one we logged usage just above)"
        )

        # Now, in present time (mock is no longer in effect)
        # call `_bootstrap_sgtk` and expect bundle deletion to be processed
        self._toolkit_mgr._bootstrap_sgtk("test_engine", None)

    def test_old_bundles_are_purged(self):
        """
        Tests that unused bundles are deleted from a call
        to the `ToolkitManager._bootstrap_sgtk` method.

        Here is the summary of the test:

        IN 'helper_test_purge_bundles':
        - Create test app_store (actually done is setUp())
        - Verify that all file are present (actually done is setUp())
        - Back in time, database is populated with content of our
          test app_store (18 fake bundles with 2 versions of 'tk-shell')
        - Check database has 18 bundles.
        - In present time we log usage of 'tk-shell/v0.5.6'
        - Call `_bootstrap_sgtk`

        HERE:
        - Expect almost everything to be deleted beside (tk-shell/v0.5.6)
        - Check database as only 1 bundle left.
        - Check that all bundles besire tk-shell/v0.5.6 are deleted.
        """

        self.helper_test_purge_bundles()

        bundle_cache_usage_purger = BundleCacheUsagePurger()

        # Check the database ...
        self.assertEquals(
            1, bundle_cache_usage_purger.bundle_count,
            "Was expecting database to have just 1 bundle left"
        )

        # ... and files ...
        # Since we've track_usage of the tk-shell/v0.5.6 bundle
        # we expect files to exists still, including, parent folder
        # and app_store folder.
        remaining_files = [
            os.path.join(self.app_store_root),
            os.path.join(self.app_store_root, "tk-shell"),
            os.path.join(self.app_store_root, "tk-shell", "v0.5.6"),
            os.path.join(self.app_store_root, "tk-shell", "v0.5.6", "info.yml")
        ]
        for f in remaining_files:
            self.assertTrue(os.path.exists(f))

    def test_old_bundles_are_purged_with_no_delete(self):
        """
        Tests that unused bundles are NOT deleted from a call
        to the `ToolkitManager._bootstrap_sgtk` method when the .
        'SHOTGUN_BUNDLE_CACHE_USAGE_NO_DELETE' env. var is defined.

        Here is the summary of the test:

        IN 'setUp():
        - Create test app_store (actually done is setUp())
        - Verify that all file are present (actually done is setUp())

        HERE:
        - Activate the 'SHOTGUN_BUNDLE_CACHE_USAGE_NO_DELETE' env. var.

        IN 'helper_test_purge_bundles()'
        - Back in time, database is populated with content of our
          test app_store (18 fake bundles with 2 versions of 'tk-shell')
        - Check database has 18 bundles.
        - In present time we log usage of 'tk-shell/v0.5.6'
        - Call `_bootstrap_sgtk`

        HERE:
        - Check database as all its entries
        - Check that all files exists
        """

        os.environ["SHOTGUN_BUNDLE_CACHE_USAGE_NO_DELETE"] = "1"

        self.helper_test_purge_bundles()

        bundle_cache_usage_purger = BundleCacheUsagePurger()

        # Check the database ...
        self.assertEquals(
            TestBundleCacheUsageBase.FAKE_TEST_BUNDLE_COUNT,
            bundle_cache_usage_purger.bundle_count,
            "Was expecting database to report all bundles"
        )

        # ... and files ... nothing should have been deleted
        app_store_file_list = self._get_app_store_file_list()
        self.assertEquals(self.FAKE_TEST_BUNDLE_FILE_COUNT, len(app_store_file_list))







