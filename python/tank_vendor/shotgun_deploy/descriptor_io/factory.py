# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from ..errors import ShotgunDeployError, ShotgunAppStoreError
from .. import constants
from .. import util
log = util.get_shotgun_deploy_logger()


def create_io_descriptor(sg, descriptor_type, location_dict, bundle_cache_root):
    """
    Factory method.

    :param sg: Shotgun connection to associated site
    :param descriptor_type: Either AppDescriptor.APP, CORE, ENGINE or FRAMEWORK
    :param bundle_cache_root: Root path to where downloaded apps are cached
    :param location_dict: A std location dictionary
    :returns: Descriptor object
    """
    from .appstore import IODescriptorAppStore
    from .dev import IODescriptorDev
    from .path import IODescriptorPath
    from .uploaded_pipeline_config import IODescriptorUploadedConfig
    from .shotgun_entity import IODescriptorShotgunEntity
    from .git import IODescriptorGit
    from .git_dev import IODescriptorGitDev
    from .manual import IODescriptorManual

    if location_dict.get("type") == "app_store":
        descriptor = IODescriptorAppStore(bundle_cache_root, location_dict, sg, descriptor_type)

    elif location_dict.get("type") == "shotgun":
        descriptor = IODescriptorShotgunEntity(bundle_cache_root, location_dict, sg)

    elif location_dict.get("type") == "manual":
        descriptor = IODescriptorManual(bundle_cache_root, location_dict)

    elif location_dict.get("type") == "git":
        descriptor = IODescriptorGit(bundle_cache_root, location_dict)

    elif location_dict.get("type") == "dev":
        descriptor = IODescriptorDev(bundle_cache_root, location_dict)

    elif location_dict.get("type") == "git_dev":
        descriptor = IODescriptorGitDev(bundle_cache_root, location_dict)

    elif location_dict.get("type") == "path":
        descriptor = IODescriptorPath(bundle_cache_root, location_dict)

    elif location_dict.get("type") == "shotgun_uploaded_configuration":
        descriptor = IODescriptorUploadedConfig(bundle_cache_root, location_dict, sg)

    else:
        raise ShotgunDeployError("Invalid location dict '%s'" % location_dict)

    log.debug("Resolved %s -> %r" % (location_dict, descriptor))

    if constants.LATEST_DESCRIPTOR_KEYWORD in location_dict.get("version"):
        log.debug("Latest keyword detected. Searching for latest version...")
        descriptor = descriptor.get_latest_version()
        log.debug("Resolved latest to be %r" % descriptor)


    return descriptor