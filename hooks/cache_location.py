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

from sgtk import Hook
from sgtk import TankError
import os
import errno
import urlparse
import sys

class CacheLocation(Hook):
    """
    Hook to control cache folder creation. 
    See execute method for details.
    
    Future Note!
    ------------
    
    If new cache modes are introduced in the Toolkit Core, any hook implementations which 
    have been specifically overridden will raise an Exception. The rationale here is that 
    if you have overridden the path cache, you most likely take an interest in where cache
    files will go (which implies you are an advanced user) and you most likely want to 
    customize the new mode that is being introduced aswell. 

    """
    
    def execute(self, project_id, pipeline_configuration_id, mode, parameters, **kwargs):
        """
        Establish a cache folder or file for a given purpose.
        
        This hooks allows for customization of where various cache data should reside on disk.
        For example, this includes the path cache database, app, engine and framework specific
        cache locations. Such app locations are often used by apps to store run-time cache files
        such as thumbnails, cached data sets etc.

        :param project_id: The shotgun id of the project to store caches for
        :param pipeline_configuration_id: The shotgun pipeline config id to store caches for
        :param mode: Mode string describing which cache location should be returned.
                     Current valid values are "path_cache" and "bundle_cache"
        :param parameters: Dictionary with mode specific parameters.
                           The following parameters are passed for the different modes:
                           - path_cache: {}
                           - bundle_cache: { "bundle": bundle_object }
        
        :returns: The path to a file or a folder (depending on mode) which should exist on disk.
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
        
        self._ensure_folder_exists(cache_root)
        
        # now establish the sub structure, this is done differently for different modes
        if mode == "path_cache":
            target_path = os.path.join(cache_root, "path_cache.db")
            self._ensure_file_exists(target_path)                
            
        elif mode == "bundle_cache":
            bundle = parameters["bundle"]
            target_path = os.path.join(cache_root, bundle.name)
            self._ensure_folder_exists(target_path)
            
        else:
            # raise an error so that users who have overridden the hook will get an error message
            # the next time we add a cache class to the hook
            raise TankError("Toolkit requested an unsupported cache item '%s'. Please update your "
                            "cache_location hook to include a behavior for this data type." % mode)
        
        return target_path
    
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
            
