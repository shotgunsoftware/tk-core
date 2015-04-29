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
from ..errors import TankError

class YamlCache(object):
    """
    Main yaml cache class
    """
    def __init__(self):
        """
        Construction
        """
        self._cache = {}
        self._lock = threading.Lock()
            
    def get(self, path):
        """
        Retrieve the yaml data for the specified path.  If it's not already
        in the cache of the cached version is out of date then this will load
        the Yaml file from disk.
        
        :param path:    The path of the yaml file to load.
        :returns:       The raw yaml data loaded from the file.
        """
        if not os.path.exists(path):
            raise TankError("File '%s' could not be found!" % path)            
        
        # get info about the file:
        fstat = os.stat(path)
        modified_at = fstat.st_mtime
        file_size = fstat.st_size
        
        # see if this file is already cached:
        cache_entry = self._get(path)
        if (not cache_entry
            or cache_entry["modified_at"] != modified_at
            or cache_entry["file_size"] != file_size):
            # try to load the file data:
            try:
                fh = open(path, "r")
            except Exception, e:
                raise TankError("Could not open file '%s'. Error reported: '%s'" % (path, e))
            
            try:
                # load the data:
                raw_data = yaml.load(fh)
                # add/update the data in the cache - note that only the latest version of the 
                # data is retained!
                cache_entry = self._add(path, raw_data, modified_at, file_size)
            except Exception, e:
                raise TankError("Could not parse file '%s'. Error reported: '%s'" % (path, e))
            finally:
                fh.close()            

        # always return a deep copy of the cached data to ensure that 
        # the cached data is not updated accidentally!:
        data = copy.deepcopy(cache_entry["data"])
        
        return data

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
            
    def _add(self, path, data, modified_at, file_size):
        """
        Add the specified data to the cache if it doesn't already exist.  If the data
        does exist in the cache with the same modified time and file size then the
        already cached version will be returned.
        This method is thread-safe.
        
        :param path:        The path of the yaml file being cached
        :param data:        The raw yaml data being cached
        :param modified_at: The time the file was last modified
        :param file_size:   The size of the yaml file
        :returns:           A dictionary containing the data, modified_at time and file size
                            of the cached data.
        """
        self._lock.acquire()
        try:
            # see if the item is already in the cache:
            cache_entry = self._cache.get(path)
            if (cache_entry
                and cache_entry["modified_at"] == modified_at
                and cache_entry["file_size"] == file_size):
                # must have been loaded by another thread so just use 
                # this one instead!
                return cache_entry
            else:
                # add new item to cache and return:
                cache_entry = {
                    "modified_at":modified_at, 
                    "file_size":file_size, 
                    "data":data
                }
                self._cache[path] = cache_entry
                return cache_entry
        finally:
            self._lock.release()

# the global instance of the YamlCache
g_yaml_cache = YamlCache()
