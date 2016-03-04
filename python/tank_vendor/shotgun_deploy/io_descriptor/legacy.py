# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""Functions in support of backward compatibility for io descriptors."""

import os
import sys
import urlparse

from tank_vendor.shotgun_deploy.errors import ShotgunDeployError

def get_legacy_path_cache_path(tk, project_id=None, pipeline_configuration_id=None):
    """Return the path cache file by looking at legacy locations.

    :param tk: Toolkit api instance
    :param project_id: The shotgun id of the project. Optional.
    :param pipeline_configuration_id: The shotgun pipeline config id. Optional.
    :rtype: str
    :return: The legacy path to the path cache.
    :raises: TankError - if no legacy path is found.
    """

    # If future backward incompatible changes are made to core, this method
    # should be modified to account for additional legacy paths.

    # --- v0.17.x

    cache_root = _get_legacy_cache_root_v017x(tk, project_id,
        pipeline_configuration_id)
    path_cache_path = os.path.join(cache_root, "path_cache.db")

    if not os.path.exists(path_cache_path):
        raise ShotgunDeployError("No legacy path cache found.")

    return path_cache_path


def get_legacy_bundle_data_cache_folder(tk, bundle, project_id=None, pipeline_configuration_id=None):
    """Return the legacy directory for bundle data caches.

    :param tk: Toolkit api instance
    :param bundle: The app, engine or framework to return the legacy cache dir for.
    :param project_id: The shotgun id of the project. Optional.
    :param pipeline_configuration_id: The shotgun pipeline config id. Optional.
    :rtype: str
    :return: The legacy directory where the bundle is cached.
    :raises: TankError - if no legacy path is found.
    """

    # If future backward incompatible changes are made to core, this method
    # should be modified to account for additional legacy paths.

    # --- v0.17.x

    legacy_cache_root = _get_legacy_cache_root_v017x(tk, project_id,
        pipeline_configuration_id)
    legacy_bundle_data_cache_folder = os.path.join(legacy_cache_root, bundle.name)

    if not os.path.exists(legacy_bundle_data_cache_folder):
        raise ShotgunDeployError("No legacy path cache found.")

    return legacy_bundle_data_cache_folder


def get_legacy_bundle_install_folder(
    descriptor_name,
    install_cache_root,
    bundle_type,
    bundle_name,
    bundle_version
):
    """Return the path to the legacy bundle install dir for the supplied info.

    :param descriptor_name: The name of the descriptor. ex: "app_store" or "git"
    :param install_cache_root: The root path to the bundle cache.
    :param bundle_type: The type of the bundle. Should be one of:
        Descriptor.APP, Descriptor.ENGINE, or Descriptor.FRAMEWORK.
    :param bundle_name: The display name for the resolved descriptor resource.
        ex: "tk-multi-shotgunpanel"
    :param bundle_version: The version of the bundle on disk. ex: "v1.2.5"
    :rtype: str
    :return: The path to the cache in the legacy bundle structure.
    :raises: ShotgunDeployError - if the bundle_type is not recognized.

    This method is provided for compatibility with older versions of core,
    prior to v0.18.x. As of v0.18.x, the bundle cache subdirectory names
    were shortened and otherwise modified to help prevent MAX_PATH issues
    on windows. This method is used to add the old style path as a fallback
    for cases like core having been upgraded to v0.18.x on an existing project.

    New style cache path:
        <root>/app_store/tk-multi-shotgunpanel/v1.2.5

    Legacy style cache path:
        <root>/apps/app_store/tk-multi-shotgunpanel/v1.2.5

    For reference, this method emulates: `tank.deploy.descriptor._get_local_location`
    in the pre-v0.18.x core.

    """

    from tank_vendor.shotgun_deploy import Descriptor

    if bundle_type == Descriptor.APP:
        legacy_dir = "apps"
    elif bundle_type == Descriptor.ENGINE:
        legacy_dir = "engines"
    elif bundle_type == Descriptor.FRAMEWORK:
        legacy_dir = "frameworks"
    else:
        raise ShotgunDeployError(
            "Unknown bundle type '%s'. Can not determine legacy cache path." %
            (bundle_type,)
        )

    # build and return the path.
    # example: <root>/apps/app_store/tk-multi-shotgunpanel/v1.2.5
    return os.path.join(
        install_cache_root,
        legacy_dir,
        descriptor_name,
        bundle_name,
        bundle_version,
    )

##############################################################################
# protected methods with version-specific core logic

def _get_legacy_cache_root_v017x(tk, project_id=None, pipeline_configuration_id=None):
    """Return the bundle cache root as defined in v0.17.x core.

    :param tk: Toolkit api instance
    :param project_id: The shotgun id of the project. Optional.
    :param pipeline_configuration_id: The shotgun pipeline config id. Optional.
    :rtype: str
    :return: The v0.17.x cache root

    """

    # the legacy v0.17.x locations are:
    # macosx: ~/Library/Caches/Shotgun/SITE_NAME/project_xxx/config_yyy
    # windows: $APPDATA/Shotgun/SITE_NAME/project_xxx/config_yyy
    # linux: ~/.shotgun/SITE_NAME/project_xxx/config_yyy

    # first establish the root location
    if sys.platform == "darwin":
        root = os.path.expanduser("~/Library/Caches/Shotgun")
    elif sys.platform == "win32":
        root = os.path.join(os.environ["APPDATA"], "Shotgun")
    elif sys.platform.startswith("linux"):
        root = os.path.expanduser("~/.shotgun")

    # get site only; https://www.foo.com:8080 -> www.foo.com
    base_url = urlparse.urlparse(tk.shotgun_url)[1].split(":")[0]

    if project_id is None:
        if tk.pipeline_configuration.is_site_configuration():
            project_id = 0
        else:
            project_id = tk.pipeline_configuration.get_project_id()

    if pipeline_configuration_id is None:
        pipeline_configuration_id = tk.pipeline_configuration.get_shotgun_id()

    # now structure things by site, project id, and pipeline config id
    return os.path.join(
        root,
        base_url,
        "project_%d" % project_id,
        "config_%d" % pipeline_configuration_id,
        )


