# Copyright (c) 2015 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Implements a caching mechanism to avoid loading the same yaml file multiple times
unless it's changed on disk.
"""

import os
import copy
import threading

from tank_vendor import yaml
from ..errors import (
    TankError,
    TankUnreadableFileError,
    TankFileDoesNotExistError,
)

class CacheItem(object):
    """
    Represents a single item in the global yaml cache.

    Each item carries with it a set of data, an stat from the .yml file that
    it was sourced from (in os.stat form), and the path to the .yml file that
    was sourced.
    """

    def __init__(self, path, data=None, stat=None):
        """
        Initializes the item.

        :param path:    The path to the .yml file on disk.
        :param data:    The data sourced from the .yml file.
        :param stat:    The stat of the file on disk. If not provided, an os.stat
                        will be run and the result stored.
        :raises:        tank.errors.TankUnreadableFileError: File stat failure.
        """
        self._path = path
        self._data = data
        try:
            self._stat = stat or os.stat(path)
        except Exception, exc:
            raise TankUnreadableFileError("Unable to stat file '%s': %s" % (path, exc))

    @property
    def data(self):
        """The item's data."""
        return self._data

    @data.setter
    def data(self, config_data):
        self._data = config_data

    @property
    def path(self):
        """The path to the file on disk that the item was sourced from."""
        return self._path

    @property
    def stat(self):
        """The stat of the file on disk that the item was sourced from."""
        return self._stat

    def given_item_newer(self, other):
        """
        Tests whether the given item is newer than this.

        :param other:   The CacheItem to test against.
        :raises:        TypeError: Given item is not a CacheItem.
        :returns:       bool, True if other is newer, False if not.
        """
        if not isinstance(other, CacheItem):
            raise TypeError("Given item must be of type CacheItem.")
        return other.stat.st_mtime > self.stat.st_mtime

    def size_differs(self, other):
        """
        Tests whether the file size of the given item differs from this item.

        :param other:   The CacheItem to test against.
        :raises:        TypeError: Given item is not a CacheItem.
        :returns:       bool, True if other is a different size on disk, False if not.
        """
        if not isinstance(other, CacheItem):
            raise TypeError("Given item must be of type CacheItem.")
        return other.stat.st_size != self.stat.st_size

    def __eq__(self, other):
        if not isinstance(other, CacheItem):
            raise TypeError("Given item must be of type CacheItem.")
        return (other.stat.st_mtime == self.stat.st_mtime and not self.size_differs(other))

    def __getitem__(self, key):
        # Backwards compatibility just in case something outside
        # of this module is expecting the old dict structure.
        if key == "modified_at":
            return self.stat.st_mtime
        elif key == "file_size":
            return self.stat.st_size
        elif key == "data":
            return self._data
        else:
            return getattr(self._data, key)

    def __str__(self):
        return str(self.path)

class YamlCache(object):
    """
    Main yaml cache class
    """
    # The cache will be a singleton. At the bottom of this
    # module is defined a global YamlCache object, which
    # will then be shared if/when other instantiations occur.
    # It's likely that most all code will be referencing the
    # global variable for the cache, but this will ensure that
    # even if that's not the case we'll still only have a single
    # cache used throughout.
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(YamlCache, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, cache_dict=None):
        """
        Construction
        """
        self._cache = cache_dict or dict()
        self._lock = threading.Lock()
            
    def get(self, path):
        """
        Retrieve the yaml data for the specified path.  If it's not already
        in the cache of the cached version is out of date then this will load
        the Yaml file from disk.
        
        :param path:    The path of the yaml file to load.
        :returns:       The raw yaml data loaded from the file.
        """
        # Adding a new CacheItem to the cache will cause the file mtime
        # and size on disk to be checked against existing cache data,
        # then the loading of the yaml data if necessary before returning
        # the appropriate item back to us, which will be either the new
        # item we have created here with the yaml data stored within, or
        # the existing cached data.
        item = self._add(CacheItem(path))

        # Always return a deep copy of the cached data to ensure that 
        # the cached data is not updated accidentally!
        return copy.deepcopy(item.data)

    def get_cached_items(self):
        return self._cache.values()

    def merge_cache_items(self, cache_items):
        """
        Merges the given CacheItem objects into the cache if they are newer
        or of a different size on disk than what's already in the cache.

        :param cache_items: A list of CacheItem objects.
        """
        for item in cache_items:
            self._add(item)

    def _get(self, path):
        """
        Return the cache entry for the specified path if it exists.  
        This method is thread-safe

        :param path:    The path of the yaml file to return the entry for
        :returns:       A dictionary containing the data, modified_at time and file size
                        of the cached data.
        """
        self._lock.acquire()
        try:
            return self._cache.get(path)
        finally:
            self._lock.release()
            
    def _add(self, item):
        """
        Adds the given item to the cache in a thread-safe way. If the given item
        is older (by file mtime) than the existing cache data for that file then
        the already-cached item will be returned. If the item is identical in
        file mtime and file size to what's cached, the already-cached item will be
        returned. Otherwise the item will be added to the cache and returned to
        the caller. If the given item is added to the cache and it has not already
        been populated with the yaml data from disk, that data will be read prior
        to the item being added to the cache.
        
        :param item:    The CacheItem to add to the cache.
        :returns:       The cached CacheItem.
        """
        self._lock.acquire()
        try:
            path = str(item)
            cached_item = self._cache.get(path)
            if cached_item and cached_item == item:
                # It's already in the cache and matches mtime
                # and file size, so we can just return what we
                # already have. It's technically identical in
                # terms of data of what we got, but it's best
                # to return the instance we have since that's
                # what previous logic in the cache did.
                return cached_item
            elif cached_item and item.given_item_newer(cached_item):
                # If the data already cached is newer (based on mtime)
                # then we don't need to add to the cache.
                return cached_item
            else:
                # Load the yaml data from disk. If it's not already populated.
                if not item.data:
                    try:
                        fh = open(path, "r")
                        raw_data = yaml.load(fh)
                    except IOError:
                        raise TankFileDoesNotExistError("File does not exist: %s" % path)
                    except Exception, e:
                        raise TankError("Could not open file '%s'. Error reported: '%s'" % (path, e))
                        # Since it wasn't an IOError it means we have an open
                        # filehandle to close.
                        fh.close()
                    # Populate the item's data before adding it to the cache.
                    item.data = raw_data
                self._cache[path] = item
                return item
        finally:
            self._lock.release()

# The global instance of the YamlCache.
g_yaml_cache = YamlCache()
