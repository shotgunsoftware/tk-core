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
from sgtk.util import filesystem, LocalFileStorageManager

HookBaseClass = sgtk.get_hook_baseclass()
log = sgtk.LogManager.get_logger(__name__)

class CacheLocation(HookBaseClass):
    """
    Hook to control cache folder creation.
    
    For further details, see individual cache methods below.
    """
    
    def get_path_cache_path(self, project_id, plugin_id, pipeline_configuration_id):
        """
        Establish a location for the path cache database file.

        This hook method was introduced in Toolkit v0.18 and replaces path_cache.
        If you already have implemented path_cache, this will be detected and called instead,
        however we strongly recommend that you tweak your hook.

        Overriding this method in a hook allows a user to change the location on disk where
        the path cache file is located. The path cache file holds a temporary cache representation
        of the FilesystemLocation entities stored in Shotgun for a project. Typically, this cache
        is stored on a local machine, separate for each user.  

        Note! In the case of the site configuration, project id will be set to None.
        In the case of an unmanaged pipeline configuration, pipeline config
        id will be set to None.

        :param project_id: The shotgun id of the project to store caches for
        :param plugin_id: Unique string to identify the scope for a particular plugin
                          or integration. For more information,
                          see :meth:`~sgtk.bootstrap.ToolkitManager.plugin_id`. For
                          non-plugin based toolkit projects, this value is None.
        :param pipeline_configuration_id: The shotgun pipeline config id to store caches for
        :returns: The path to a path cache file. This file should exist when this method returns.
        """
        # backwards compatibility with custom hooks created before 0.18
        if hasattr(self, "path_cache") and callable(getattr(self, "path_cache")):
            # there is a custom version of the legacy hook path_cache
            log.warning(
                "Detected old core cache hook implementation. "
                "It is strongly recommended that this is upgraded."
            )

            # call legacy hook to make sure we call the custom
            # implementation that is provided by the user.
            # this implementation expects project id 0 for
            # the site config, so ensure that's the case too
            if project_id is None:
                project_id = 0

            return self.path_cache(project_id, pipeline_configuration_id)


        cache_filename = "path_cache.db"

        tk = self.parent

        cache_root = LocalFileStorageManager.get_configuration_root(
            tk.shotgun_url,
            project_id,
            plugin_id,
            pipeline_configuration_id,
            LocalFileStorageManager.CACHE
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
        legacy_cache_root = LocalFileStorageManager.get_configuration_root(
            tk.shotgun_url,
            project_id,
            plugin_id,
            pipeline_configuration_id,
            LocalFileStorageManager.CACHE,
            generation=LocalFileStorageManager.CORE_V17
        )

        legacy_target_path = os.path.join(legacy_cache_root, cache_filename)

        if os.path.exists(legacy_target_path):
            # legacy path cache file exists, return it
            return legacy_target_path

        # neither new style or legacy path cache exists. use the new style
        filesystem.ensure_folder_exists(cache_root)
        filesystem.touch_file(target_path)

        return target_path

    def get_bundle_data_cache_path(self, project_id, plugin_id, pipeline_configuration_id, bundle):
        """
        Establish a cache folder for an app, engine or framework.

        This hook method was introduced in Toolkit v0.18 and replaces bundle_cache.
        If you already have implemented bundle_cache, this will be detected and called instead,
        however we strongly recommend that you tweak your hook.
        
        Apps, Engines or Frameworks commonly caches data on disk. This can be 
        small files, shotgun queries, thumbnails etc. This method implements the 
        logic which defines this location on disk. The cache should be organized in 
        a way so that all instances of the app can re-use the same data. (Apps 
        which needs to cache things per-instance can implement this using a sub
        folder inside the bundle cache location).

        It is possible to omit some components of the path by explicitly passing
        a `None` value for them, only the bundle name is required. For example,
        with `project_id=None`, a site level cache path will be returned.
        Ommitting the `project_id` can be used to cache data for the site
        configuration, or to share data accross all projects belonging to a
        common site.

        :param project_id: The shotgun id of the project to store caches for, or None.
        :param plugin_id: Unique string to identify the scope for a particular plugin
                          or integration, or None. For more information,
                          see :meth:`~sgtk.bootstrap.ToolkitManager.plugin_id`. For
                          non-plugin based toolkit projects, this value is None.
        :param pipeline_configuration_id: The shotgun pipeline config id to store caches for, or None.
        :param bundle: The app, engine or framework object which is requesting the cache folder.
        :returns: The path to a folder which should exist on disk.
        """
        # backwards compatibility with custom hooks created before 0.18
        if hasattr(self, "bundle_cache") and callable(getattr(self, "bundle_cache")):
            # there is a custom version of the legacy hook path_cache
            log.warning(
                "Detected old core cache hook implementation. "
                "It is strongly recommended that this is upgraded."
            )

            # call legacy hook to make sure we call the custom
            # implementation that is provided by the user.
            # this implementation expects project id 0 for
            # the site config, so ensure that's the case too
            if project_id is None:
                project_id = 0

            return self.bundle_cache(project_id, pipeline_configuration_id, bundle)


        tk = self.parent
        cache_root = LocalFileStorageManager.get_configuration_root(
            tk.shotgun_url,
            project_id,
            plugin_id,
            pipeline_configuration_id,
            LocalFileStorageManager.CACHE
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
            # new style cache bundle folder exists, return it
            return target_path

        # The target path does not exist. This could be because it just hasn't
        # been created yet, or it could be because of a core upgrade where the
        # cache root directory structure has changed (such is the case with
        # v0.17.x -> v0.18.x). To account for this scenario, see if the target
        # exists in an old location first, and if so, return that path instead.
        legacy_cache_root = LocalFileStorageManager.get_configuration_root(
            tk.shotgun_url,
            project_id,
            plugin_id,
            pipeline_configuration_id,
            LocalFileStorageManager.CACHE,
            generation=LocalFileStorageManager.CORE_V17
        )
        legacy_target_path = os.path.join(legacy_cache_root, bundle.name)

        if os.path.exists(legacy_target_path):
            # legacy cache bundle folder exists, return it
            return legacy_target_path

        # neither new style or legacy path cache exists. use the new style
        filesystem.ensure_folder_exists(target_path)

        return target_path

