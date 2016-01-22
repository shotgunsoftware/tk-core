# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

from ..shotgun_base import get_cache_root, ensure_folder_exists
from .errors import ShotgunDeployError

def _get_bundle_cache_root():
    """
    Returns the cache location for the global bundle cache.
    Ensures that this folder exists

    :returns: path on disk
    """
    bundle_cache_root = os.path.join(get_cache_root(), "bundle_cache")
    ensure_folder_exists(bundle_cache_root)
    return bundle_cache_root


def create_descriptor(sg_connection, descriptor_type, location_dict, bundle_cache_root=None):
    """
    Factory method.

    :param sg_connection: Shotgun connection to associated site
    :param descriptor_type: Either AppDescriptor.APP, CORE, ENGINE or FRAMEWORK
    :param bundle_cache_root: Root path to where downloaded apps are cached
    :param location_dict: A std location dictionary
    :returns: Descriptor object
    """

    bundle_cache_root = bundle_cache_root or _get_bundle_cache_root()

    from .app_store_descriptor import AppStoreDescriptor
    from .dev_descriptor import DevDescriptor
    from .git_descriptor import GitDescriptor
    from .manual_descriptor import ManualDescriptor

    # tank app store format
    # location: {"type": "app_store", "name": "tk-nukepublish", "version": "v0.5.0"}
    if location_dict.get("type") == "app_store":
        return AppStoreDescriptor(sg_connection, bundle_cache_root, location_dict, descriptor_type)

    # manual format
    # location: {"type": "manual", "name": "tk-nukepublish", "version": "v0.5.0"}
    elif location_dict.get("type") == "manual":
        return ManualDescriptor(bundle_cache_root, location_dict, descriptor_type)

    # git repo
    # location: {"type": "git", "path": "/path/to/repo.git", "version": "v0.2.1"}
    elif location_dict.get("type") == "git":
        return GitDescriptor(bundle_cache_root, location_dict, descriptor_type)

    # local dev format - for example
    # location: {"type": "dev", "path": "/path/to/app"}
    elif location_dict.get("type") == "dev":
        return DevDescriptor(bundle_cache_root, location_dict)

    else:
        raise ShotgunDeployError("%s: Invalid location dict '%s'" % (descriptor_type, location_dict))

