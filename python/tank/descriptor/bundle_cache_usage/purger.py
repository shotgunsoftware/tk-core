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

from ...import LogManager
from database import BundleCacheUsageDatabase
from errors import BundleCacheUsageError
from errors import BundleCacheUsageFileDeletionError

log = LogManager.get_logger(__name__)


class BundleCacheUsagePurger(object):

    """
    Bundle cache usage utility class for discovering existing bundle packages and deleting unused ones.

    .. note:: All execution of this code is occuring in the main foreground thread.
    """

    def __init__(self):
        super(BundleCacheUsagePurger, self).__init__()
        self._database = BundleCacheUsageDatabase()

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
        bundle_cache_root = self.bundle_cache_root

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

    def _find_bundles(self):
        """
        Search the bundle cache for bundle descriptors and add them
        as unused entries to the database.

        Reference: Walk up to a certain level
        https://stackoverflow.com/questions/42720627/python-os-walk-to-certain-level

        :return: a list of bundle path
        """

        app_store_bundle_list = self._find_app_store_bundles()
        # TODO: Process other bundle_cache sub folders

        return app_store_bundle_list

    def _get_filelist(self, bundle_path):
        """
        Returns a list of files existing under the specified bundle path.
        :param bundle_path: a valid path to a bundle cache bundle
        :return: a list of path
        """
        # Restore bundle full path which was truncated and set relative to 'bundle_cache_root'
        full_bundle_path = os.path.join(self.bundle_cache_root, bundle_path)
        if not os.path.exists(full_bundle_path):
            raise BundleCacheUsageError("The specified path does not exists: %s" % (full_bundle_path))

        file_list = []
        for (dirpath, dirnames, filenames) in os.walk(full_bundle_path):
            file_list.append(dirpath)
            for filename in filenames:
                fullpath = os.path.join(dirpath, filename)
                file_list.append(fullpath)

        return file_list

    def _paranoid_delete(self, filelist):
        """
        Delete files and folder under the specified filelist in a paranoid mode where
        everything is carrefully checked before deleteion. That means no 'rmtree'-like
        operation, no walking and deleting items directly.

        On anything unexpected the process stops with a custom exception.

        We cannot delete file right away. The list being in reverse order, we might be
        trying to delete a file that exists in a symlinked folder. Therefore, we'll first
        scan the entire list for a link, symlink or such in the list. If found, we'll
        abort the deletion process before actually deleting anything.

        :param filelist: A list file and folders to be deleted
        """

        # First, check whether there is a symlink in the list
        for f in filelist:
            if os.path.islink(f):
                # CAVEAT: Always False if symbolic links are not supported by the Python runtime.
                #         How do we know whether it is supported???
                raise BundleCacheUsageFileDeletionError(f, "Found a symlink")

        # We have a crude list, now we need to sort it out in reverse
        # order so we can later on delete files, and then parent folder
        # in a logical order.
        rlist = list(reversed(filelist))
        # No symlinks, Houston we're clear for deletion
        for f in rlist:
            if not os.path.exists(f):
                raise BundleCacheUsageFileDeletionError(
                    "Attempting to delete non existing file or folder: %s" % (f)
                )

            if os.path.isfile(f):
                os.remove(f)

            elif os.path.isdir(f):
                # Because we're deleting items that should be reverse prdered
                # when we're about to delete a folder, it should be empty already.
                # let's check it out!
                try:
                    os.rmdir(f)
                except OSError as e:
                    raise BundleCacheUsageFileDeletionError(
                        "Attempted to delete a non-empty folder: %s (%s)" % (f, e)
                    )

            else:
                raise BundleCacheUsageFileDeletionError(
                    "Not a link, not a file, not a directory ??? : %s" % (f)
                )

    ###################################################################################################################
    #
    # PUBLIC API - methods & properties
    #
    # Can be called from any threading contextes (main or worker)
    #
    ###################################################################################################################

    @property
    def bundle_cache_root(self):
        """
        Returns the path to the typical global bundle cache root folder.
        """
        return self._database.bundle_cache_root

    @property
    def bundle_count(self):
        """
        Returns an integer of the number of currently tracked bundles in the database
        """
        return self._database.bundle_count

    @LogManager.log_timing
    def initial_populate(self):
        """
        Performs the initial-one-time search for bundles in the bundle cache and populate
        the database as unused entries.
        """
        log.info("Searching for existing bundles ...")
        found_bundles = self._find_bundles()
        for bundle_path in found_bundles:
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
                self.bundle_cache_root,
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
            filelist = self._get_filelist(bundle.path)
            self._paranoid_delete(filelist)
            # No exception, everything was deleted

            # Try deleting parent dir if now empty
            parent_dir = os.path.abspath(
                os.path.join(self.bundle_cache_root, bundle.path, os.pardir)
            )
            if not os.listdir(parent_dir):
                os.rmdir(parent_dir)

            #  Finally, delete the database entry
            self._database.delete_entry(bundle)
            log.debug("Deleted bundle '%s'" % str(bundle.path))

        except Exception as e:
            log.error("Error deleting the following bundle:%s exception:%s" % (bundle.path, e))
