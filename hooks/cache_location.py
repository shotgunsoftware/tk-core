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
import sys
import urlparse

from tank_vendor.shotgun_base import get_pipeline_config_cache_root

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
            legacy_path_cache = self._get_legacy_path_cache(
                project_id, pipeline_configuration_id)
        except TankError:
            # legacy path cache does not exist. ensure original target exists.
            self._ensure_folder_exists(cache_root)
            self._ensure_file_exists(target_path)
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

        # ---- backward compatibility for old bundle cache locations

        # The target path does not exist. This could be because it just hasn't
        # been created yet, or it could be because of a core upgrade where the
        # bundle cache directory structure has changed (such is the case with
        # v0.17.x -> v0.18.x). To account for this scenario, see if the target
        # exists in an old location first, and if so, return that path instead.

        try:
            legacy_path_cache = self._get_legacy_bundle_cache(
                project_id, pipeline_configuration_id, bundle)
        except TankError:
            # legacy bundle cache does not exist. ensure original target exists.
            self._ensure_folder_exists(target_path)
        else:
            # legacy path exists, make it the target
            target_path = legacy_path_cache

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

    def _get_legacy_cache_root_v017x(self, project_id, pipeline_configuration_id):
        """Return the path cache root as defined in v0.17.x core.

        :param project_id: The shotgun id of the project to store caches for
        :param pipeline_configuration_id: The shotgun pipeline config id to store caches for
        :rtype: str
        :return: The v0.17.x cache root

        """

        # the legacy v0.17.x locations are:
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
        base_url = urlparse.urlparse(tk.shotgun_url)[1].split(":")[0]

        # now structure things by site, project id, and pipeline config id
        return os.path.join(
            root,
            base_url,
            "project_%d" % project_id,
            "config_%d" % pipeline_configuration_id,
        )

    def _get_legacy_path_cache(self, project_id, pipeline_configuration_id):
        """Return the path cache file by looking at legacy locations.

        :param project_id: The shotgun id of the project to store caches for
        :param pipeline_configuration_id: The shotgun pipeline config id to store caches for
        :rtype: str
        :return: The legacy path to the path cache.
        :raises: TankError - if no legacy path is found.
        """

        # If future backward incompatible changes are made to core, this method
        # should be modified to account for additional legacy paths.

        # --- v0.17.x

        cache_root = self._get_legacy_cache_root_v017x(project_id,
            pipeline_configuration_id)
        path_cache = os.path.join(cache_root, "path_cache.db")

        if not os.path.exists(path_cache):
            raise TankError("No legacy path cache found.")

        return path_cache

    def _get_legacy_bundle_cache(self, project_id, pipeline_configuration_id, bundle):
        """Return the bundle cache file by looking at legacy locations.

        :param project_id: The shotgun id of the project to store caches for
        :param pipeline_configuration_id: The shotgun pipeline config id to store caches for
        :param bundle: The app, engine or framework object which is requesting the cache folder.
        :rtype: str
        :return: The legacy path to the bundle cache.
        :raises: TankError - if no legacy path is found.
        """

        # If future backward incompatible changes are made to core, this method
        # should be modified to account for additional legacy paths.

        # --- v0.17.x

        cache_root = self._get_legacy_cache_root_v017x(project_id,
                                                       pipeline_configuration_id)
        path_cache = os.path.join(cache_root, bundle.name)

        if not os.path.exists(path_cache):
            raise TankError("No legacy path cache found.")

        return path_cache

