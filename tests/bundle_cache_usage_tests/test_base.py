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


class TestBundleCacheUsageBase(unittest2.TestCase):
    """
    TestBundleCacheUsageBase test base class
    """
    TMP_FOLDER_PREFIX = "TestBundleCacheUsageBase_"
    EXPECTED_DEFAULT_DB_FILENAME = "bundle_usage.db"

    def setUp(self):
        # Actually we don't want to inherit from tanTestBase
        super(TestBundleCacheUsageBase, self).setUp()
        #use_fix_folder = "/var/folders/4j/xfybtxms23bgfv0_m9zs4zw00000gs/T/tankTemporary_k8tom0/TestBundleCacheUsageBase_"
        use_fix_folder = None

        # TODO: cleanup when completed
        current_tmp_root = tempfile.tempdir
        if use_fix_folder:
            self._temp_folder = use_fix_folder
        else:
            self._temp_folder = os.path.join(tempfile.tempdir, TestBundleCacheUsageBase.TMP_FOLDER_PREFIX)

        if not os.path.exists(self._temp_folder):
            os.mkdir(self._temp_folder)

        self._expected_db_path = os.path.join(self._temp_folder,
                                              TestBundleCacheUsageBase.EXPECTED_DEFAULT_DB_FILENAME)

        # Preventively delete leftovers
        self.delete_db()

    def tearDown(self):
        super(TestBundleCacheUsageBase, self).tearDown()
        Utils.safe_delete(self._temp_folder)

    @property
    def bundle_cache_root(self):
        return self._temp_folder

    @classmethod
    def _create_test_bundle_cache(cls, root_folder):
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
            os.remove(self.db_path)

    @property
    def db(self):
        if self._db:
            return self._db

        raise Exception("The test database is null, was it created?")

    @property
    def expected_db_path(self):
        return self._expected_db_path
