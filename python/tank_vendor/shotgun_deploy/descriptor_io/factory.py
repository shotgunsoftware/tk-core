# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import urllib
from ..errors import ShotgunDeployError
from .. import constants
from .. import util
log = util.get_shotgun_deploy_logger()

def create_io_descriptor(sg, descriptor_type, location, bundle_cache_root):
    """
    Factory method. Use this method to construct all DescriptorIO instances.

    :param sg: Shotgun connection to associated site
    :param descriptor_type: Either AppDescriptor.APP, CORE, ENGINE or FRAMEWORK
    :param location: A std location dictionary dictionary or string
    :param bundle_cache_root: Root path to where downloaded apps are cached
    :returns: Descriptor object
    """
    from .appstore import IODescriptorAppStore
    from .dev import IODescriptorDev
    from .path import IODescriptorPath
    from .shotgun_entity import IODescriptorShotgunEntity
    from .git import IODescriptorGit
    from .git_branch import IODescriptorGitBranch
    from .manual import IODescriptorManual


    if isinstance(location, basestring):
        # translate uri to dict
        location_dict = _uri_to_dict(location)
    else:
        location_dict = location

    if location_dict.get("type") == "app_store":
        descriptor = IODescriptorAppStore(bundle_cache_root, location_dict, sg, descriptor_type)

    elif location_dict.get("type") == "shotgun":
        descriptor = IODescriptorShotgunEntity(bundle_cache_root, location_dict, sg)

    elif location_dict.get("type") == "manual":
        descriptor = IODescriptorManual(bundle_cache_root, location_dict)

    elif location_dict.get("type") == "git":
        descriptor = IODescriptorGit(bundle_cache_root, location_dict)

    elif location_dict.get("type") == "git_branch":
        descriptor = IODescriptorGitBranch(bundle_cache_root, location_dict)

    elif location_dict.get("type") == "dev":
        descriptor = IODescriptorDev(bundle_cache_root, location_dict)

    elif location_dict.get("type") == "path":
        descriptor = IODescriptorPath(bundle_cache_root, location_dict)

    else:
        raise ShotgunDeployError("Unknown location type for '%s'" % location_dict)

    if location_dict.get("version") == constants.LATEST_DESCRIPTOR_KEYWORD:
        log.debug("Latest keyword detected. Searching for latest version...")
        descriptor = descriptor.get_latest_version()
        log.debug("Resolved latest to be %r" % descriptor)

    return descriptor


def _uri_to_dict(location_uri):
    """
    Translates a location uri into a location dictionary, suitable for
    use with the create_io_descriptor factory method below.

    :param location_uri: location string uri
    :returns: location dictionary
    """
    chunks = location_uri.split(":")
    if chunks[0] != "sgtk" or len(chunks) < 3:
        raise ShotgunDeployError("Invalid uri %s" % location_uri)
    descriptor_type = urllib.unquote(chunks[1])

    location_dict = {}
    location_dict["type"] = descriptor_type

    if descriptor_type == "app_store":
        # sgtk:app_store:tk-core:v12.3.4
        location_dict["name"] = urllib.unquote(chunks[2])
        location_dict["version"] = urllib.unquote(chunks[3])

    elif descriptor_type == "shotgun":
        # sgtk:shotgun:PipelineConfiguration:sg_config:primary:p123:v456 # with project id
        # sgtk:shotgun:PipelineConfiguration:sg_config:primary::v456     # without project id
        location_dict["entity_type"] = urllib.unquote(chunks[2])
        location_dict["field"] = urllib.unquote(chunks[3])
        location_dict["name"] = urllib.unquote(chunks[4])

        if chunks[5].startswith("p"):
            project_str = urllib.unquote(chunks[5])
            location_dict["project_id"] = int(project_str[1:])

        version_str = urllib.unquote(chunks[6])
        location_dict["version"] = int(version_str[1:])

    elif descriptor_type == "manual":
        # sgtk:manual:tk-core:v12.3.4
        location_dict["name"] = urllib.unquote(chunks[2])
        location_dict["version"] = urllib.unquote(chunks[3])

    elif descriptor_type == "git":
        # sgtk:git:git/path:v12.3.4
        location_dict["path"] = urllib.unquote(chunks[2])
        location_dict["version"] = urllib.unquote(chunks[3])

    elif descriptor_type == "git_branch":
        # sgtk:git_branch:git/path:branchname:commithash
        location_dict["path"] = urllib.unquote(chunks[2])
        location_dict["branch"] = urllib.unquote(chunks[3])
        location_dict["version"] = urllib.unquote(chunks[4])

    elif descriptor_type == "dev" or descriptor_type == "dev3":
        # sgtk:dev:[name]:local_path
        # sgtk:dev3:[name]:win_path:linux_path:mac_path
        #
        # Examples:
        # sgtk:dev:my-app:/tmp/foo/bar
        # sgtk:dev3::c%3A%0Coo%08ar:/tmp/foo/bar:

        if chunks[2] != "":
            # there is a name defined
            location_dict["name"] = urllib.unquote(chunks[2])

        if chunks[1] == "dev":
            # local path descriptor
            location_dict["path"] = urllib.unquote(chunks[3])
        else:
            # three os format
            if chunks[3] != "":
                location_dict["windows_path"] = urllib.unquote(chunks[3])
            if chunks[4] != "":
                location_dict["linux_path"] = urllib.unquote(chunks[4])
            if chunks[5] != "":
                location_dict["mac_path"] = urllib.unquote(chunks[5])

    elif descriptor_type == "path" or descriptor_type == "path3":
        # sgtk:path:[name]:local_path
        # sgtk:path3:[name]:win_path:linux_path:mac_path
        #
        # Examples:
        # sgtk:path:my-app:/tmp/foo/bar
        # sgtk:path3::c%3A%0Coo%08ar:/tmp/foo/bar:

        if chunks[2] != "":
            # there is a name defined
            location_dict["name"] = urllib.unquote(chunks[2])

        if chunks[1] == "path":
            # local path descriptor
            location_dict["path"] = urllib.unquote(chunks[3])
        else:
            # three os format
            if chunks[3] != "":
                location_dict["windows_path"] = urllib.unquote(chunks[3])
            if chunks[4] != "":
                location_dict["linux_path"] = urllib.unquote(chunks[4])
            if chunks[5] != "":
                location_dict["mac_path"] = urllib.unquote(chunks[5])

    else:
        raise ShotgunDeployError("Unknown location type for '%s'" % location_dict)

    return location_dict


