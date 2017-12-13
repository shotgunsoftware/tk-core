# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.


class BundleCacheUsageWriterBase(object):

    def __init__(self, bundle_cache_root):
        self._bundle_cache_root = bundle_cache_root

    def add_unused_bundle(self, bundle_path):
        """
        Add an entry to the database which usage count is initialized with zero.
        :param bundle_path: a str path to a bundle cache item
        """
        raise NotImplementedError()

    @property
    def bundle_cache_root(self):
        """
        Returns the path to the cache bundle this instance was initialized with.
        :return: A str path t bundle cache folder.
        """
        return self._bundle_cache_root

    def close(self):
        """
        Close the database connection.
        """
        raise NotImplementedError()

    def delete_entry(self, bundle_path):
        """
        Delete the specified entry from the database
        and the bundle cache usage database.
        :param path: a str path of an entry to be deleted from database
        """
        raise NotImplementedError()

    def get_bundle_count(self):
        """
        Returns the number of bundles tracked in the database.
        :return: An integer of a tracked bundle count
        """
        raise NotImplementedError()

    def get_last_usage_date(self, bundle_path):
        raise NotImplementedError()

    def get_last_usage_timestamp(self, bundle_path):
        raise NotImplementedError()

    def log_usage(self, bundle_path):
        """
        Increase the database usage count and access date for the specified entry.
        If the entry was not in the database already, the usage count will be
        initialized to 1.

        NOTE: The specified path is truncated and relative to the `bundle_cache_root` property.

        :param bundle_path: A str path to a bundle
        """
        raise NotImplementedError()

    @property
    def path(self):
        """
        Returns the full path & filename to the database for this instance.
        NOTE: The filename is not cleared on closing the database.
        :return: A string of the path & filename to the database file.
        """
        raise NotImplementedError()