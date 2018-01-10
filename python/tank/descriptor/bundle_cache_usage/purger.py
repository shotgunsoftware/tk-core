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

from ... import LogManager
from ...util.filesystem import safe_delete_folder
from .database import BundleCacheUsageDatabase
from errors import BundleCacheTrackingError
from errors import BundleCacheTrackingFileDeletionError

log = LogManager.get_logger(__name__)


class BundleCacheUsagePurger(object):
    """
    Bundle cache usage utility class for discovering existing bundle packages and deleting unused ones.

    .. note:: All execution of this code is occuring in the main foreground thread.
    """

    def __init__(self):
        """
        Initialize a  :class:`~sgtk.descriptor.bundle_cache_usage.purger.BundleCacheUsagePurger` instance
        """
        super(BundleCacheUsagePurger, self).__init__()
        self._database = BundleCacheUsageDatabase()

    @property
    def _bundle_cache_root(self):
        """
        Returns the path to the typical global bundle cache root folder.
        """
        return self._database.bundle_cache_root

    @property
    def _bundle_count(self):
        """
        Returns an integer of the number of currently tracked bundles in the database
        """
        return self._database.bundle_count

    @classmethod
    def _find_app_store_path(cls, base_folder):
        """
        Searches for the 'app_store' folder starting from teh specified folder
        and return its path.

        :param base_folder: A str path to start the search from
        :return: A str path or None
        """
        for (dirpath, dirnames, filenames) in os.walk(base_folder):
            if dirpath.endswith('app_store'):
                return dirpath

        return None

    @classmethod
    def _find_descriptors(cls, base_folder, max_walk_depth):
        """
        Search the specified folder for bundle descriptors.

        .. note:: To prevent returning plugins or deeper files, the search is limited to
        a certain depth.

        :param base_folder: a str path to start the search from
        :param max_walk_depth: an int maximum path depth to search into
        :return: a list of bundle path
        """
        path_list = []
        base_folder_len = len(base_folder)
        for (dirpath, dirnames, filenames) in os.walk(base_folder):
            shopped_base_path = dirpath[base_folder_len + 1:]
            level_down_count = shopped_base_path.count(os.sep)
            if level_down_count <= max_walk_depth:
                for filename in filenames:
                    if filename.endswith('info.yml'):
                        path_list.append(dirpath)

        return path_list

    def _find_app_store_bundles(self):
        """
         Search for bundle descriptors in the `app_store` folder.

        :return: a list of bundle path
        """
        # TODO: Find a tk-core reference about why MAX_DEPTH_WALK should be set to 2
        MAX_DEPTH_WALK = 2

        bundle_path_list = []
        bundle_cache_root = self._bundle_cache_root

        # Process the local app store first
        bundle_cache_app_store = BundleCacheUsagePurger._find_app_store_path(bundle_cache_root)

        if bundle_cache_app_store:
            if bundle_cache_app_store and \
                    os.path.exists(bundle_cache_app_store) and \
                    os.path.isdir(bundle_cache_app_store):

                log.debug("Found local app store path: %s" % (bundle_cache_app_store))
                bundle_path_list += BundleCacheUsagePurger._find_descriptors(bundle_cache_app_store, MAX_DEPTH_WALK)
        else:
            log.debug("Could not find the local app store path from: %s" % (bundle_cache_root))

        return bundle_path_list

    ###################################################################################################################
    #
    # PUBLIC API - methods & properties
    #
    # Can be called from any threading contextes (main or worker)
    #
    ###################################################################################################################

    @LogManager.log_timing
    def initial_populate(self):
        """
        Performs the initial-one-time search for bundles in the bundle cache and populate
        the database as unused entries.
        """
        log.debug("Searching for existing bundles ...")
        found_bundle_path_list = self._find_app_store_bundles()
        for bundle_path in found_bundle_path_list:
            log.debug("Adding bundle '%s' to database" % (bundle_path))
            self._database.add_unused_bundle(bundle_path)

        log.debug("populating done, found %d entries" % (len(found_bundle_path_list)))
        self._database.initial_populate_performed = True

    @property
    def initial_populate_performed(self):
        """
        Returns a boolean true if the initial database population was performed else False
        """
        return self._database.initial_populate_performed

    def get_unused_bundles(self, since_days=60):
        """
        Returns the list of bundles unused in the specified number of days.

        :param since_days: an int count of days
        :return: A list of :class:`~BundleCacheUsageDatabaseEntry`
        """
        log.debug(
            "Generating list of items in '%s' that haven't been accessed for %d or more days." % (
                self._bundle_cache_root,
                since_days
            )
        )

        oldest_timestamp = self._database._get_timestamp() - (since_days * 24 * 3600)
        return self._database.get_unused_bundles(oldest_timestamp)

    def purge_bundle(self, bundle):
        """
        Delete both files and database entry relating to the specified bundle.

        :param bundle: a :class:`~BundleCacheUsageDatabaseEntry` instance
        """
        try:
            log.debug(
                "Removing bundle '%s' from disk, last accessed on %s" % (
                    (
                        os.path.join(self.bundle_cache_root, bundle.path),
                        bundle.last_usage_date_formatted
                    )
                )
            )

            if not os.path.exists(bundle.path):
                raise BundleCacheTrackingError("The specified path does not exists: %s" % (bundle.path))

            if not os.path.isdir(bundle.path):
                raise BundleCacheTrackingError("The specified path is not a diectorys: %s" % (bundle.path))

            if not bundle.path.startsWith(self._bundle_cache_root):
                raise BundleCacheTrackingError("The specified directory is not under global bundle cache: %s" % (bundle.path))

            safe_delete_folder(bundle.path)
            # No exception, everything was deleted

            # Try deleting parent dir if now empty
            parent_dir = os.path.abspath(
                os.path.join(self.bundle_cache_root, bundle.path, os.pardir)
            )
            # Not using 'safe_delete_folder' for the safety of deleting the wrong folder.
            if not os.listdir(parent_dir):
                os.rmdir(parent_dir)

            #  Finally, delete the database entry
            self._database.delete_entry(bundle)

        except Exception as e:
            log.error("Error deleting the following bundle:%s exception:%s" % (bundle.path, e))
