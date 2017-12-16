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
import time
import datetime
import threading

from worker import BundleCacheUsageWorker
from exception import BundleCacheUsageException
from exception import BundleCacheUsageFileDeletionException
from . import BundleCacheUsageLogger as log


class BundleCacheManager(object):

    """
    Bungle utility class for scanning, purging a bundle packages in the bundle cache
    """

    # keeps track of the single instance of the class
    __singleton_lock = threading.Lock()
    __singleton_instance = None

    def __new__(cls, *args, **kwargs):
        #
        # Based on tornado.ioloop.IOLoop.instance() approach.
        #
        # See:
        #   https://github.com/facebook/tornado
        #   https://gist.github.com/werediver/4396488
        #   https://en.wikipedia.org/wiki/Double-checked_locking
        #
        if not cls.__singleton_instance:
            log.debug_manager("__new__")
            with cls.__singleton_lock:
                if not cls.__singleton_instance:
                    cls.__singleton_instance = super(BundleCacheManager, cls).__new__(cls, *args, **kwargs)
                    cls.__singleton_instance.__initialized = False

        return cls.__singleton_instance

    def __init__(self, bundle_cache_root):
        super(BundleCacheManager, self).__init__()
        log.debug_manager("__init__('%s')" % bundle_cache_root)
        # TODO: returning would cause a silent non-usage of specified parameter
        if (self.__initialized):
            return
        self._worker = None

        if bundle_cache_root is None:
            raise ValueError("The 'bundle_cache_root' parameter is None.")

        if not os.path.exists(bundle_cache_root):
            raise OSError(
                "The specified 'bundle_cache_root' parameter folder does not exists: %s" % (bundle_cache_root)
            )

        if not os.path.isdir(bundle_cache_root):
            raise OSError(
                "The specified 'bundle_cache_root' parameter is not a directory." % (bundle_cache_root)
            )

        self._bundle_cache_root = bundle_cache_root
        self._worker = BundleCacheUsageWorker(bundle_cache_root)
        self._worker.start()
        self.__initialized = True

    @classmethod
    def delete_instance(cls):
        with cls.__singleton_lock:
            if cls.__singleton_instance:
                if cls.__singleton_instance._worker:
                    cls.__singleton_instance._worker.stop()
                    cls.__singleton_instance = None

    @classmethod
    def _find_app_store_path(cls, base_folder):
        for (dirpath, dirnames, filenames) in os.walk(base_folder):
            if dirpath.endswith('app_store'):
                return dirpath

        return None

    @classmethod
    def _find_descriptors(cls, base_folder, max_walk_depth):
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
        # TODO: Find a tk-core reference about why MAX_DEPTH_WALK should be set to 2
        MAX_DEPTH_WALK = 2

        bundle_path_list = []
        bundle_cache_root = self.bundle_cache_root

        # Process the local app store first
        bundle_cache_app_store = BundleCacheManager._find_app_store_path(bundle_cache_root)

        if bundle_cache_app_store:
            log.debug("Found local app store path: %s" % (bundle_cache_app_store))

            if bundle_cache_app_store and \
                    os.path.exists(bundle_cache_app_store) and \
                    os.path.isdir(bundle_cache_app_store):

                log.debug("Found local app store path: %s" % (bundle_cache_app_store))
                bundle_path_list += BundleCacheManager._find_descriptors(bundle_cache_app_store, MAX_DEPTH_WALK)
        else:
            log.debug("Could not find the local app store path from: %s" % (bundle_cache_root))

        return bundle_path_list

    def _find_bundles(self):
        """
        Scan the bundle cache at the specified location for bundles and add them
        as unused entries to the database.

        Reference: Walk up to a certain level
        https://stackoverflow.com/questions/42720627/python-os-walk-to-certain-level

        :param bundle_cache_root: A str of a path
        """

        app_store_bundle_list = self._find_app_store_bundles()
        # TODO: Process other bundle_cache sub folders
        bundle_list2 = []
        bundle_list3 = []

        # Combine all lists into a single one
        bundle_path_list = list(set(app_store_bundle_list + bundle_list2 + bundle_list3))

        return bundle_path_list

    def _get_filelist(self, bundle_path):

        # Restore bundle full path which was truncated and set relative to 'bundle_cache_root'
        full_bundle_path = os.path.join(self.bundle_cache_root, bundle_path)
        if not os.path.exists(full_bundle_path):
            raise BundleCacheUsageException("","The specified path does not exists: %s" % (full_bundle_path))

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
                raise BundleCacheUsageFileDeletionException(f, "Found a symlink")

        # We have a crude list, now we need to sort it out in reverse
        # order so we can later on delete files, and then parent folder
        # in a logical order.
        rlist = list(reversed(filelist))
        # No symlinks, Houston we're clear for deletion
        for f in rlist:
            if not os.path.exists(f):
                raise BundleCacheUsageFileDeletionException(
                    f,
                    "Attempting to delete non existing file or folder."
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
                    raise BundleCacheUsageFileDeletionException(
                        f,
                        "Attempted to delete a non-empty folder: %s" % (e)
                    )

            else:
                raise BundleCacheUsageFileDeletionException(
                    f,
                    "Not a link, not a file, not a directory ???"
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
        return self._bundle_cache_root

    def initial_populate(self):
        """
        Scan the bundle cache at the specified location for bundles and add them
        as unused entries to the database.

        """

        log.info("Searching for existing bundles ...")
        start_time = time.time()
        found_bundles = self._find_bundles()
        for bundle_path in found_bundles:
            self._worker.add_unused_bundle(bundle_path)

        log.info("populating done in %ss, found %d entries" % (
            time.time() - start_time, len(found_bundles)
        ))

    @property
    def initial_populate_performed(self):
        """
        :return: bool True if the initial database population was performed else False
        """
        # TODO: replace with unenbigouos INITIAL_POPULATE_NOT_DONE record.
        return self.get_bundle_count()>0

    def get_bundle_count(self):
        return self._worker.get_bundle_count()

    def get_last_usage_date(self, bundle_path):
        return datetime.datetime.fromtimestamp(
            self.get_last_usage_timestamp(bundle_path)
        ).isoformat()

    def get_last_usage_timestamp(self, bundle_path):
        return self._worker.get_last_usage_timestamp(bundle_path)

    def get_unused_bundles(self, since_days=60):
        return self._worker.get_unused_bundles(since_days)

    def get_usage_count(self, bundle_path):
        return self._worker.get_usage_count(bundle_path)

    @classmethod
    def log_usage(cls, bundle_path):
        with cls.__singleton_lock:
            if cls.__singleton_instance:
                if cls.__singleton_instance._worker:
                    cls.__singleton_instance._worker.log_usage(bundle_path)

    def purge_bundle(self, bundle_path):
        try:
            filelist = self._get_filelist(bundle_path)
            self._paranoid_delete(filelist)
            # No exception, everything was deleted, delete the entry from database
            self._worker.delete_entry(bundle_path)
            log.debug("Deleted bundle '%s'" % str(bundle_path))
        except Exception as e:
            log.error("Error deleting the following bundle:%s exception:%s" % (bundle_path, e))
