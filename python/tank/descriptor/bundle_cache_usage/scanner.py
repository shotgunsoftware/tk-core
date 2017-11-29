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


class BundleCacheScanner(object):
    """
    A simple utility class for scanning bundle packages in the bundle cache
    """
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
    def find_app_store_path(cls, base_folder):
        for (dirpath, dirnames, filenames) in os.walk(base_folder):
            if dirpath.endswith('app_store'):
                return dirpath

        return None

    @classmethod
    def find_bundles(cls, bundle_cache_root):
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

        MAX_DEPTH_WALK = 2

        log.debug("find_bundles: populating ...")
        start_time = time.time()
        bundle_path_list = []

        if bundle_cache_root and \
                os.path.exists(bundle_cache_root) and \
                os.path.isdir(bundle_cache_root):
                    bundle_cache_dirs = os.listdir(bundle_cache_root)
                    for sub_dir in bundle_cache_dirs:
                        path = os.path.join(bundle_cache_root, sub_dir)
                        if os.path.isdir(path):
                            bundle_path_list += cls._find_descriptors(path, MAX_DEPTH_WALK)

        elapsed_time = time.time() - start_time
        log.info("find_bundles: populating done in %ss, found %d entries" % (
            elapsed_time, len(bundle_path_list)
        ))
        return bundle_path_list
