# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

def create_descriptor(descriptor_type, app_cache_root, location_dict):
    """
    Factory method.

    :param descriptor_type: Either AppDescriptor.APP, CORE, ENGINE or FRAMEWORK
    :param app_cache_root: Root path to where downloaded apps are cached
    :param location_dict: A std location dictionary
    :returns: Descriptor object
    """
    from .app_store_descriptor import AppStoreDescriptor
    from .dev_descriptor import DevDescriptor
    from .git_descriptor import GitDescriptor
    from .manual_descriptor import ManualDescriptor

    # tank app store format
    # location: {"type": "app_store", "name": "tk-nukepublish", "version": "v0.5.0"}
    if location_dict.get("type") == "app_store":
        return AppStoreDescriptor(app_cache_root, location_dict, descriptor_type)

    # manual format
    # location: {"type": "manual", "name": "tk-nukepublish", "version": "v0.5.0"}
    elif location_dict.get("type") == "manual":
        return ManualDescriptor(app_cache_root, location_dict, descriptor_type)

    # git repo
    # location: {"type": "git", "path": "/path/to/repo.git", "version": "v0.2.1"}
    elif location_dict.get("type") == "git":
        return GitDescriptor(app_cache_root, location_dict, descriptor_type)

    # local dev format
    # location: {"type": "dev", "path": "/path/to/app"}
    # or
    # location: {"type": "dev", "windows_path": "c:\\path\\to\\app", "linux_path": "/path/to/app", "mac_path": "/path/to/app"}
    elif location_dict.get("type") == "dev":
        return DevDescriptor(app_cache_root, location_dict)

    else:
        raise TankError("%s: Invalid location dict '%s'" % (descriptor_type, location_dict))

