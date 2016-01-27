# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

def create_io_descriptor(sg, descriptor_type, location_dict, bundle_cache_root):
    """
    Factory method.

    :param sg_connection: Shotgun connection to associated site
    :param descriptor_type: Either AppDescriptor.APP, CORE, ENGINE or FRAMEWORK
    :param bundle_cache_root: Root path to where downloaded apps are cached
    :param location_dict: A std location dictionary
    :returns: Descriptor object
    """
    from .appstore import IODescriptorAppStore
    from .dev import IODescriptorDev
    from .git import IODescriptorGit
    from .manual import IODescriptorManual

    if location_dict.get("type") == "app_store":
        return IODescriptorAppStore(bundle_cache_root, location_dict, sg, descriptor_type)

    elif location_dict.get("type") == "manual":
        return IODescriptorManual(bundle_cache_root, location_dict)

    elif location_dict.get("type") == "git":
        return IODescriptorGit(bundle_cache_root, location_dict)

    elif location_dict.get("type") == "dev":
        return IODescriptorDev(bundle_cache_root, location_dict)

    else:
        raise ShotgunDeployError("Invalid location dict '%s'" % location_dict)