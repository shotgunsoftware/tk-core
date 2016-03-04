# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from ..errors import ShotgunDeployError
from .. import constants
from .. import util
log = util.get_shotgun_deploy_logger()

def create_io_descriptor(sg, descriptor_type, location, bundle_cache_root, fallback_roots):
    """
    Factory method. Use this method to construct all DescriptorIO instances.

    :param sg: Shotgun connection to associated site
    :param descriptor_type: Either AppDescriptor.APP, CORE, ENGINE or FRAMEWORK
    :param location: A std location dictionary dictionary or string
    :param bundle_cache_root: Root path to where downloaded apps are cached
    :param fallback_roots: List of immutable fallback cache locations where
                           apps will be searched for. Note that when descriptors
                           download new content, it always ends up in the
                           bundle_cache_root.
    :returns: Descriptor object
    """
    from .base import IODescriptorBase
    from .appstore import IODescriptorAppStore
    from .dev import IODescriptorDev
    from .path import IODescriptorPath
    from .shotgun_entity import IODescriptorShotgunEntity
    from .git_tag import IODescriptorGitTag
    from .git_branch import IODescriptorGitBranch
    from .manual import IODescriptorManual

    if isinstance(location, basestring):
        # translate uri to dict
        location_dict = IODescriptorBase.dict_from_uri(location)
    else:
        location_dict = location

    if location_dict.get("type") == "app_store":
        descriptor = IODescriptorAppStore(location_dict, sg, descriptor_type)

    elif location_dict.get("type") == "shotgun":
        descriptor = IODescriptorShotgunEntity(location_dict, sg)

    elif location_dict.get("type") == "manual":
        descriptor = IODescriptorManual(location_dict, descriptor_type)

    elif location_dict.get("type") == "git":
        descriptor = IODescriptorGitTag(location_dict, descriptor_type)

    elif location_dict.get("type") == "git_branch":
        descriptor = IODescriptorGitBranch(location_dict)

    elif location_dict.get("type") == "dev":
        descriptor = IODescriptorDev(location_dict)

    elif location_dict.get("type") == "path":
        descriptor = IODescriptorPath(location_dict)

    else:
        raise ShotgunDeployError("Unknown location type for '%s'" % location_dict)

    # specify where to go look for caches
    descriptor.set_cache_roots(bundle_cache_root, fallback_roots)

    if location_dict.get("version") == constants.LATEST_DESCRIPTOR_KEYWORD:
        log.debug("Latest keyword detected. Searching for latest version...")
        descriptor = descriptor.get_latest_version()
        log.debug("Resolved latest to be %r" % descriptor)

    return descriptor

def location_uri_to_dict(location_uri):
    """
    Translates a location uri into a location dictionary, suitable for
    use with the create_io_descriptor factory method below.

    :param location_uri: location string uri
    :returns: location dictionary
    """
    from .base import IODescriptorBase
    return IODescriptorBase.dict_from_uri(location_uri)

def location_dict_to_uri(location_dict):
    """
    Translates a location dictionary into a location uri.

    :param location_dict: location dictionary
    :returns: location uri
    """
    from .base import IODescriptorBase
    return IODescriptorBase.uri_from_dict(location_dict)
