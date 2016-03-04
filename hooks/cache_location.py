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
import os

from tank_vendor.shotgun_base import get_pipeline_config_cache_root
from tank_vendor.shotgun_base.utils import (
    ensure_file_exists,
    ensure_folder_exists,
)
from tank_vendor.shotgun_deploy.errors import ShotgunDeployError
from tank_vendor.shotgun_deploy.io_descriptor.legacy import (
    get_legacy_path_cache_path,
    get_legacy_bundle_data_cache_folder,
)

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

        Note! In the case of the site configuration, project id will be set to None.
        In the case of an unmanaged pipeline configuration, pipeline config
        id will be set to None.

        :param project_id: The shotgun id of the project to store caches for
        :param pipeline_configuration_id: The shotgun pipeline config id to store caches for
        :returns: The path to a path cache file. This file should exist when this method returns.
        """
        tk = self.parent
        cache_root = get_pipeline_config_cache_root(
            tk.shotgun_url,
            project_id,
            pipeline_configuration_id
        )

        target_path = os.path.join(cache_root, "path_cache.db")

        if os.path.exists(target_path):
            # path exists, return it
            return target_path

        # ---- backward compatibility for old path cache locations

        # The target path does not exist. This could be because it just hasn't
        # been created yet, or it could be because of a core upgrade where the
        # cache root directory structure has changed (such is the case with
        # v0.17.x -> v0.18.x). To account for this scenario, see if the target
        # exists in an old location first, and if so, return that path instead.

        try:
            legacy_path_cache = get_legacy_path_cache_path(tk, project_id,
                pipeline_configuration_id)
        except ShotgunDeployError:
            # legacy path cache does not exist. ensure original target exists.
            ensure_folder_exists(cache_root)
            ensure_file_exists(target_path)
        else:
            # legacy path exists, make it the target
            target_path = legacy_path_cache
        
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

        NOTE: This method may be slightly confusing given the use of the term
        "bundle_cache" throughout core which refers to the location on disk
        where bundles (apps, engines, frameworks) are installed. A better
        name for this method might have been `bundle_data_cache`. The name
        remains to avoid breaking client code.

        """
        tk = self.parent
        cache_root = get_pipeline_config_cache_root(
            tk.shotgun_url,
            project_id,
            pipeline_configuration_id
        )

        # in the interest of trying to minimize path lengths (to avoid
        # the MAX_PATH limit on windows, we apply some shortcuts
        
        # if the bundle is a framework, we shorten it:
        # tk-framework-shotgunutils --> fw-shotgunutils        
        # if the bundle is a multi-app, we shorten it:
        # tk-multi-workfiles2 --> tm-workfiles2
        bundle_name = bundle.name
        bundle_name = bundle_name.replace("tk-framework-", "fw-")
        bundle_name = bundle_name.replace("tk-multi-", "tm-")

        target_path = os.path.join(cache_root, bundle_name)

        if os.path.exists(target_path):
            # path exists, return it
            return target_path

        # ---- backward compatibility for old bundle data cache locations

        # The target path does not exist. This could be because it just hasn't
        # been created yet, or it could be because of a core upgrade where the
        # bundle cache directory structure has changed (such is the case with
        # v0.17.x -> v0.18.x). To account for this scenario, see if the target
        # exists in an old location first, and if so, return that path instead.

        try:
            legacy_path_cache = get_legacy_bundle_data_cache_folder(tk, bundle,
                project_id, pipeline_configuration_id)
        except ShotgunDeployError:
            # legacy bundle cache does not exist. ensure original target exists.
            ensure_folder_exists(target_path)
        else:
            # legacy path exists, make it the target
            target_path = legacy_path_cache

        return target_path

