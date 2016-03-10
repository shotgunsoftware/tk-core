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

from tank_vendor.shotgun_base import (
    get_pipeline_config_cache_root,
    get_legacy_pipeline_config_cache_root,
    get_cache_bundle_folder_name,
)

from tank_vendor.shotgun_base import touch_file, ensure_folder_exists

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

        cache_filename = "path_cache.db"

        tk = self.parent
        cache_root = get_pipeline_config_cache_root(
            tk.shotgun_url,
            project_id,
            pipeline_configuration_id
        )

        target_path = os.path.join(cache_root, cache_filename)

        if os.path.exists(target_path):
            # new style path cache file exists, return it
            return target_path

        # The target path does not exist. This could be because it just hasn't
        # been created yet, or it could be because of a core upgrade where the
        # cache root directory structure has changed (such is the case with
        # v0.17.x -> v0.18.x). To account for this scenario, see if the target
        # exists in an old location first, and if so, return that path instead.
        legacy_cache_root = get_legacy_pipeline_config_cache_root(
            tk.shotgun_url,
            project_id,
            pipeline_configuration_id
        )
        legacy_target_path = os.path.join(legacy_cache_root, cache_filename)

        if os.path.exists(legacy_target_path):
            # legacy path cache file exists, return it
            return legacy_target_path

        # neither new style or legacy path cache exists. use the new style
        ensure_folder_exists(cache_root)
        touch_file(target_path)

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
            pipeline_configuration_id,
        )
        target_path = os.path.join(cache_root, get_cache_bundle_folder_name(bundle))

        if os.path.exists(target_path):
            # new style cache bundle folder exists, return it
            return target_path

        # The target path does not exist. This could be because it just hasn't
        # been created yet, or it could be because of a core upgrade where the
        # cache root directory structure has changed (such is the case with
        # v0.17.x -> v0.18.x). To account for this scenario, see if the target
        # exists in an old location first, and if so, return that path instead.
        legacy_cache_root = get_legacy_pipeline_config_cache_root(
            tk.shotgun_url,
            project_id,
            pipeline_configuration_id,
        )
        legacy_target_path = os.path.join(legacy_cache_root, bundle.name)

        if os.path.exists(legacy_target_path):
            # legacy cache bundle folder exists, return it
            return legacy_target_path

        # neither new style or legacy path cache exists. use the new style
        ensure_folder_exists(target_path)

        return target_path

