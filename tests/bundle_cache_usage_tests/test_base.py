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

    #
    # An excerpt from chapter of Jules Verne' TWENTY THOUSAND LEAGUES UNDER THE SEA
    #
    # Ref: https://www.gutenberg.org/files/164/164-h/164-h.htm
    text_data = \
        "The year 1866 was signalised by a remarkable incident, a mysterious and" \
        "puzzling phenomenon, which doubtless no one has yet forgotten. Not to mention" \
        "rumours which agitated the maritime population and excited the public mind, "\
        " even in the interior of continents, seafaring men were particularly excited." \
        "Merchants, common sailors, captains of vessels, skippers, both of Europe and "\
        "America, naval officers of all countries, and the Governments of several States "\
        "on the two continents, were deeply interested in the matter." \
        "For some time past vessels had been met by an enormous thing, a long object, "\
        "spindle-shaped,occasionally phosphorescent, and infinitely larger and more rapid" \
        "its movements than a whale. The facts relating to this apparition (entered in"\
        "various log-books) agreed in most respects as to the shape of the object or "\
        "creature in question, the untiring rapidity of its movements, its surprising "\
        "power of locomotion, and the peculiar life with which it seemed endowed. If it "\
        "was a whale, it surpassed in size all those hitherto classified in science. "\
        "Taking into consideration the mean of observations made at divers times?"\
        "rejecting the timid estimate of those who assigned to this object a length of two "\
        "hundred feet, equally with the exaggerated opinions which set it down as a mile in "\
        "width and three in length?we might fairly conclude that this mysterious being surpassed"\
        "greatly all dimensions admitted by the learned ones of the day, if it existed"\
        "at all. And that it DID exist was an undeniable fact; and, with that tendency"\
        "which disposes the human mind in favour of the marvellous, we can understand"\
        "the excitement produced in the entire world by this supernatural apparition."\
        "As to classing it in the list of fables, the idea was out of the question."

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

    @classmethod
    def safe_delete(cls, path):
        if path and os.path.exists(path):
            if os.path.isdir(path):
                try:
                    shutil.rmtree(path)
                except Exception as e:
                    pass

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
    DEBUG = False

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
            self._temp_folder = os.path.join(tempfile.tempdir,
                                             TestBundleCacheUsageBase.TMP_FOLDER_PREFIX)

        if not os.path.exists(self._temp_folder):
            os.makedirs(self._temp_folder)

        self._expected_db_path = os.path.join(self.bundle_cache_root,
                                              TestBundleCacheUsageBase.EXPECTED_DEFAULT_DB_FILENAME)

        TestBundleCacheUsageBase._create_test_bundle_cache(self._temp_folder)

        # Preventively delete leftovers
        self.delete_db()

    def tearDown(self):
        super(TestBundleCacheUsageBase, self).tearDown()
        Utils.safe_delete(self._temp_folder)

    @property
    def bundle_cache_root(self):
        return os.path.join(self._temp_folder, "bundle_cache")

    def log_debug(self, msg):
        if TestBundleCacheUsageBase.DEBUG:
            print("%s: %s" % (self.__class__, msg))

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
        if not os.path.exists(bundle_cache_root):
            os.makedirs(bundle_cache_root)

        cls._create_test_app_store_cache(bundle_cache_root)


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
            #Utils.touch(item)
            Utils.write_bogus_data(item)

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
