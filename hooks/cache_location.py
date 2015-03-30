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
Hook to control the various cache locations in the system.
"""

import sgtk
from sgtk import TankError
import os
import errno
import urlparse
import sys

HookBaseClass = sgtk.get_hook_baseclass()

class CacheLocation(HookBaseClass):
    """
    Hook to control cache folder creation.
    
    For further details, see individual cache methods below.
    """
    
    def path_cache(self, project_id, pipeline_configuration_id):
        """
        Establish a location for the path cache database file.
        
        Overriding this method in a hook allows a user to change the location on disk where
        the path cache file is located. The path cache file holds a temporary cache representation
        of the FilesystemLocation entities stored in Shotgun for a project. Typically, this cache
        is stored on a local machine, separate for each user.  
        
        :param project_id: The shotgun id of the project to store caches for
        :param pipeline_configuration_id: The shotgun pipeline config id to store caches for
        :returns: The path to a path cache file. This file should exist when this method returns.
        """
        cache_root = self._get_cache_root(project_id, pipeline_configuration_id)
        self._ensure_folder_exists(cache_root)
        target_path = os.path.join(cache_root, "path_cache.db")
        self._ensure_file_exists(target_path)
        
        return target_path
    
    def bundle_cache(self, project_id, pipeline_configuration_id, bundle):
        """
        Establish a cache folder for an app, engine or framework.
        
        Apps, Engines or Frameworks commonly caches data on disk. This can be 
        small files, shotgun queries, thumbnails etc. This method implements the 
        logic which defines this location on disk. The cache should be organized in 
        a way so that all instances of the app can re-use the same data. (Apps 
        which needs to cache things per-instance can implement this using a sub
        folder inside the bundle cache location).

        :param project_id: The shotgun id of the project to store caches for
        :param pipeline_configuration_id: The shotgun pipeline config id to store caches for
        :param bundle: The app, engine or framework object which is requesting the cache folder.
        :returns: The path to a folder which should exist on disk.
        """
        cache_root = self._get_cache_root(project_id, pipeline_configuration_id)
        target_path = os.path.join(cache_root, bundle.name)
        self._ensure_folder_exists(target_path)
        
        return target_path
        
    def _get_cache_root(self, project_id, pipeline_configuration_id):
        """
        Helper method that can be used both by subclassing hooks
        and inside this base level hook. This method calculates the cache root
        for the current project and configuration. In the default implementation,
        all the different types of cache data resides below a common root point. 
        
        :param project_id: The shotgun id of the project to store caches for
        :param pipeline_configuration_id: The shotgun pipeline config id to store caches for
        :returns: The calculated location for the cache root
        """
        
        # the default implementation will place things in the following locations:
        # macosx: ~/Library/Caches/Shotgun/SITE_NAME/project_xxx/config_yyy
        # windows: $APPDATA/Shotgun/SITE_NAME/project_xxx/config_yyy
        # linux: ~/.shotgun/SITE_NAME/project_xxx/config_yyy
        
        # first establish the root location
        tk = self.parent
        if sys.platform == "darwin":
            root = os.path.expanduser("~/Library/Caches/Shotgun")
        elif sys.platform == "win32":
            root = os.path.join(os.environ["APPDATA"], "Shotgun")
        elif sys.platform.startswith("linux"):
            root = os.path.expanduser("~/.shotgun")

        # get site only; https://www.foo.com:8080 -> www.foo.com
        base_url = urlparse.urlparse(tk.shotgun.base_url)[1].split(":")[0]
        
        # now structure things by site, project id, and pipeline config id
        cache_root = os.path.join(root, 
                                  base_url, 
                                  "project_%d" % project_id,
                                  "config_%d" % pipeline_configuration_id)
        return cache_root
    
    def _ensure_file_exists(self, path):
        """
        Helper method - creates a file if it doesn't already exists
        
        :param path: path to create
        """
        if not os.path.exists(path):
            old_umask = os.umask(0)
            try:
                fh = open(path, "wb")
                fh.close()
                os.chmod(path, 0666)
            except OSError, e:
                # Race conditions are perfectly possible on some network storage setups
                # so make sure that we ignore any file already exists errors, as they 
                # are not really errors!
                if e.errno != errno.EEXIST: 
                    raise TankError("Could not create cache file '%s': %s" % (path, e))
            finally:
                os.umask(old_umask)
    
    def _ensure_folder_exists(self, path):
        """
        Helper method - creates a folder if it doesn't already exists
        
        :param path: path to create
        """
        if not os.path.exists(path):
            old_umask = os.umask(0)
            try:
                os.makedirs(path, 0777)
            except OSError, e:
                # Race conditions are perfectly possible on some network storage setups
                # so make sure that we ignore any file already exists errors, as they 
                # are not really errors!
                if e.errno != errno.EEXIST: 
                    raise TankError("Could not create cache folder '%s': %s" % (path, e))
            finally:
                os.umask(old_umask)
            
