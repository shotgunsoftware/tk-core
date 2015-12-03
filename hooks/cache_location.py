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
import datetime
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
        
        # in the interest of trying to minimize path lengths (to avoid
        # the MAX_PATH limit on windows, we apply some shortcuts
        
        # if the bundle is a framework, we shorten it:
        # tk-framework-shotgunutils --> fw-shotgunutils        
        bundle_name = bundle.name
        if bundle_name.startswith("tk-framework-"):
            bundle_name = "fw-%s" % bundle_name[len("tk-framework-"):]
        
        # if the bundle is a multi-app, we shorten it:
        # tk-multi-workfiles2 --> tm-workfiles2        
        bundle_name = bundle.name
        if bundle_name.startswith("tk-multi-"):
            bundle_name = "tm-%s" % bundle_name[len("tk-multi-"):]

        target_path = os.path.join(cache_root, bundle_name)
        self._ensure_folder_exists(target_path)
        
        return target_path
        
    def global_app_cache(self):
        """
        A location where toolkit stores apps, engines and frameworks
        for all projects. 

        This setting will be used for all projects which has got the
        global app cache flag set. If the flag is not set, apps will be
        picked up from the conventional loation, local to where the core
        API installation is.

        Note that this method is called from a pipeline configuration
        object and that self.parent resolves to the current
        pipeline configuration object rather than the tk object which 
        is normally the case for core hooks.
        
        :returns: The path to a location where all projects and sites
                  can store apps, engines and frameworks.
                  This folder should exist on disk.
        """
        sg_cache_root = self._get_shotgun_cache_root()
        app_cache_root = os.path.join(sg_cache_root, "tk_app_cache")
        self._ensure_folder_exists(app_cache_root)
        return app_cache_root
        
    def managed_config(self, project_id, pipeline_configuration_id):
        """
        Establish a location for where managed configs (cloud based configs)
        are stored.
        
        Overriding this method in a hook allows a user to change the location on disk where
        managed configs are stored for a site. Managed configs are created by
        the tank synchronize command.  
        
        :param project_id: The shotgun id of the project to store caches for
        :param pipeline_configuration_id: The shotgun pipeline config id to store caches for
        :returns: The path to where a managed config location on disk should be
                  created. This folder should exist on disk.
        """
        cache_root = self._get_cache_root(project_id, pipeline_configuration_id)
        cfg_root = os.path.join(cache_root, "cfg")
        self._ensure_folder_exists(cfg_root)
        return cfg_root
        
    def managed_config_backup(self, project_id, pipeline_configuration_id):
        """
        Establish a location for where backups of managed configs (cloud based configs)
        are stored.
        
        Overriding this method in a hook allows a user to change the location on disk where
        managed configs are stored for a site. Managed configs are created by
        the tank synchronize command.  
        
        :param project_id: The shotgun id of the project to store caches for
        :param pipeline_configuration_id: The shotgun pipeline config id to store caches for
        :returns: The path to where a managed config location on disk should be
                  created. This folder should exist on disk.
        """
        cache_root = self._get_cache_root(project_id, pipeline_configuration_id)
        cfg_root = os.path.join(cache_root, "cfg.%s" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
        self._ensure_folder_exists(cfg_root)
        return cfg_root

    def _get_shotgun_cache_root(self):
        """
        Returns a cache root suitable for all Shotgun related data, 
        regardless of site.
        
        Helper method that can be used both by subclassing hooks
        and inside this base level hook.        
        
        :returns: The calculated location for the cache root
        """
        # the default implementation will place things in the following locations:
        # macosx: ~/Library/Caches/Shotgun
        # windows: %APPDATA%\Shotgun
        # linux: ~/.shotgun
        
        # first establish the root location
        if sys.platform == "darwin":
            root = os.path.expanduser("~/Library/Caches/Shotgun")
        elif sys.platform == "win32":
            root = os.path.join(os.environ["APPDATA"], "Shotgun")
        elif sys.platform.startswith("linux"):
            root = os.path.expanduser("~/.shotgun")

        return root
    
    def _get_site_cache_root(self):
        """
        Returns a cache root suitable for all Shotgun related
        data for the current shotgun site.
        
        Helper method that can be used both by subclassing hooks
        and inside this base level hook.        
        
        :returns: The calculated location for the cache root
        """
        # the default implementation will place things in the following locations:
        # macosx: ~/Library/Caches/Shotgun/SITE_NAME
        # windows: %APPDATA%\Shotgun\SITE_NAME
        # linux: ~/.shotgun/SITE_NAME
        
        # get site only; https://www.foo.com:8080 -> www.foo.com
        tk = self.parent
        base_url = urlparse.urlparse(tk.shotgun_url)[1].split(":")[0]
        
        # in order to apply further shortcuts to avoid hitting 
        # MAX_PATH on windows, strip shotgunstudio.com from all
        # hosted sites
        #
        # mysite.shotgunstudio.com -> mysite
        # shotgun.internal.int     -> shotgun.internal.int
        #
        if base_url.endswith("shotgunstudio.com"):
            base_url = base_url[:-len(".shotgunstudio.com")]
        
        return os.path.join(self._get_shotgun_cache_root(), base_url)

    def _get_cache_root(self, project_id, pipeline_configuration_id):
        """
        Calculates the cache root for the current project and configuration. 
        
        Helper method that can be used both by subclassing hooks
        and inside this base level hook.        
        
        :param project_id: The shotgun id of the project to store caches for
        :param pipeline_configuration_id: The shotgun pipeline config id to store caches for
        :returns: The calculated location for the cache root
        """
        # the default implementation will place things in the following locations:
        # macosx: ~/Library/Caches/Shotgun/SITE_NAME/p123c456
        # windows: %APPDAT%\Shotgun\SITE_NAME\p123c456
        # linux: ~/.shotgun/SITE_NAME/p123c456
        
        project_config_folder = "p%dc%d" % (project_id, pipeline_configuration_id)     
        cache_root = os.path.join(self._get_site_cache_root(), project_config_folder)
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
            
