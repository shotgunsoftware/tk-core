# Copyright (c) 2013 Shotgun Software Inc.
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
import threading

from worker import BundleCacheUsageWorker
from ...util import LocalFileStorageManager
from ... import LogManager

log = LogManager.get_logger(__name__)

class BundleCacheManagerDeletionException(Exception):

    def __init__(self, filepath, message=None):
        super(BundleCacheManagerDeletionException, self).__init__(message)
        self._filepath = filepath

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
            log.debug("__new__")
            with cls.__singleton_lock:
                if not cls.__singleton_instance:
                    cls.__singleton_instance = super(BundleCacheManager, cls).__new__(cls, *args, **kwargs)
                    cls.__singleton_instance.__initialized = False

        return cls.__singleton_instance

    def __init__(self, bundle_cache_root):
        super(BundleCacheManager, self).__init__()
        log.debug("__init__")
        #TODO: returning would cause a silent non-usage of specified parameter
        if (self.__initialized): return
        self._worker = None

        if bundle_cache_root is None:
            raise ValueError("The 'bundle_cache_root' parameter is None.")

        if not os.path.exists(bundle_cache_root):
            raise ValueError("The specified 'bundle_cache_root' parameter folder does not exists.")

        if not os.path.isdir(bundle_cache_root):
            raise ValueError("The specified 'bundle_cache_root' parameter is not a directory.")

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

    @property
    def bundle_cache_root(self):
        return self._bundle_cache_root

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

    @classmethod
    def _find_app_store_path(cls, base_folder):
        for (dirpath, dirnames, filenames) in os.walk(base_folder):
            if dirpath.endswith('app_store'):
                return dirpath

        return None
    @classmethod
    def _get_filelist(cls, path):

        file_list = []
        for (dirpath, dirnames, filenames) in os.walk(path):
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
                raise BundleCacheManagerDeletionException(f, "Found a symlink")

        # We have a crude list, now we need to sort it out in reverse
        # order so we can later on delete files, and then parent folder
        # in a logical order.
        rlist = list(reversed(filelist))
        # No symlinks, Houston we're clear for deletion
        for f in rlist:
            if not os.path.exists(f):
                raise BundleCacheManagerDeletionException(f, "Attempting to delete non existing file or folder.")

            if os.path.isfile(f):
                os.remove(f)

            elif os.path.isdir(f):
                # Because we're deleting items that should be reverse prdered
                # when we're about to delete a folder, it should be empty already.
                # let's check it out!
                try:
                    os.rmdir(f)
                except OSError as e:
                    raise BundleCacheManagerDeletionException(f, "Attempted to delete a non-empty folder")

            else:
                raise BundleCacheManagerDeletionException(f, "Not a link, not a file, not a directory ???")


    def find_bundles(self):
        """
        Scan the bundle cache at the specified location for bundles and add them
        as unused entries to the database.

        Reference: Walk up to a certain level
        https://stackoverflow.com/questions/42720627/python-os-walk-to-certain-level

        :param bundle_cache_root: A str of a path
        """

        # TODO: Find a tk-core reference about why MAX_DEPTH_WALK should be set to 2
        MAX_DEPTH_WALK = 2

        log.debug("find_bundles: populating ...")
        start_time = time.time()
        bundle_path_list = []
        bundle_cache_root = self.bundle_cache_root
        if bundle_cache_root and \
                os.path.exists(bundle_cache_root) and \
                os.path.isdir(bundle_cache_root):
                    bundle_cache_dirs = os.listdir(bundle_cache_root)
                    for sub_dir in bundle_cache_dirs:
                        path = os.path.join(bundle_cache_root, sub_dir)
                        if os.path.isdir(path):
                            bundle_path_list += BundleCacheManager._find_descriptors(path, MAX_DEPTH_WALK)

        elapsed_time = time.time() - start_time
        log.info("find_bundles: populating done in %ss, found %d entries" % (
            elapsed_time, len(bundle_path_list)
        ))


        return bundle_path_list

    def purge_unused_entries_in_last_days(self, days):
        """
        if os.path.exists(bundle_path) \
                - and os.path.isdir(bundle_path):
            -  # TODO: WARNING!!!!
        -  # last chance, add some extra checks to
        -  # make sure we never delete anything below
        -  # a certain base folder
        -                    safe_delete_folder(bundle_path)
        -                    log.debug("Deleted bundle '%s'" % str(bundle_path))
        -
        -  # Delete DB entry
        -                self._delete_bundle_entry(bundle_path)
        -                log.debug("Purged bundle '%s'" % str(bundle_path))
        -
        -            except Exception as e:
        -                log.error("Error deleting bundle package: '%s'" % (bundle_path))
        -                log.exception(e)
        +            self._delete_bundle_entry(path)
        +            log.debug_db_delete("Delete bundle entry '%s'" % str(path))
        """
