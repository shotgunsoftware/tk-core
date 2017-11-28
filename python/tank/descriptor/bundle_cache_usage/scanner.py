# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Methods relating to the Path cache, a central repository where metadata about
all Tank items in the file system are kept.

"""

import os
import time
from ... import LogManager


log = LogManager.get_logger(__name__)


class Timer(object):
    def __init__(self):
        self._start_time = time.time()
        self._stop_time = None

    @property
    def elapsed(self):
        if self.stopped:
            return self._stop_time - self._start_time
        else:
            now = time.time()
            return now - self._start_time

    @property
    def elapsed_msg(self):
        return "Elapsed: %s seconds" % ( str(self.elapsed))

    def stop(self):
        self._stop_time = time.time()

    @property
    def stopped(self):
        return self._stop_time is not None


class BundleCacheScanner(object):
    """
    A simple utility class for scanning bundle packages in the bundle cache
    """

    @classmethod
    def find_app_store_path(cls, base_folder):
        for (dirpath, dirnames, filenames) in os.walk(base_folder):
            if dirpath.endswith('app_store'):
                return dirpath

        return None

    @classmethod
    def find_bundles(cls, bundle_cache_root, MAX_DEPTH_WALK=2):
        """
        Scan the bundle cache (specified at object creation) for bundles and add them to the database
        Scan the bundle cache (specified at object creation) for bundles and add them to the database

        TODO: Find a tk-core reference about why MAX_DEPTH_WALK should be set to 2
        """

        # Initial version, although I know already this is not exactly what
        # I want since we do want to leave a folder upon finding a info.yml file.
        # https://stackoverflow.com/a/2922878/710183

        #
        # Walk up to a certain level
        # https://stackoverflow.com/questions/42720627/python-os-walk-to-certain-level

        log.debug("find_bundles: populating ...")
        t = Timer()

        bundle_path_list = []
        bundle_cache_app_store = cls.find_app_store_path(bundle_cache_root)

        if bundle_cache_app_store:
            for (dirpath, dirnames, filenames) in os.walk(bundle_cache_app_store):
                if dirpath[len(bundle_cache_app_store) + 1:].count(os.sep) <= MAX_DEPTH_WALK:
                    for filename in filenames:
                        if filename.endswith('info.yml'):
                            bundle_path_list.append(dirpath)

        log.info("find_bundles: populating done, %s, found %d entries" % (t.elapsed_msg, len(bundle_path_list)))
        return bundle_path_list
