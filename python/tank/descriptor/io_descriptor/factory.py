# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import copy

from ..errors import TankDescriptorError

from ... import LogManager
log = LogManager.get_logger(__name__)


def create_io_descriptor(
        sg,
        descriptor_type,
        dict_or_uri,
        bundle_cache_root,
        fallback_roots,
        resolve_latest,
        constraint_pattern=None):
    """
    Factory method. Use this method to construct all DescriptorIO instances.

    A descriptor is immutable in the sense that it always points at the same code -
    this may be a particular frozen version out of that toolkit app store that
    will not change or it may be a dev area where the code can change. Given this,
    descriptors are cached and only constructed once for a given descriptor URL.

    :param sg: Shotgun connection to associated site
    :param descriptor_type: Either AppDescriptor.APP, CORE, ENGINE or FRAMEWORK
    :param dict_or_uri: A std descriptor dictionary dictionary or string
    :param bundle_cache_root: Root path to where downloaded apps are cached
    :param fallback_roots: List of immutable fallback cache locations where
                           apps will be searched for. Note that when descriptors
                           download new content, it always ends up in the
                           bundle_cache_root.
    :param resolve_latest: If true, the latest version will be determined and returned.
                           If set to True, no version information need to be supplied with
                           the descriptor dictionary/uri. Please note that setting this flag
                           to true will typically affect performance - an external connection
                           is often required in order to establish what the latest version is.

                           If a remote connection cannot be established when attempting to determine
                           the latest version, a local scan will be carried out and the highest
                           version number that is cached locally will be returned.
    :param constraint_pattern: If resolve_latest is True, this pattern can be used to constrain
                           the search for latest to only take part over a subset of versions.
                           This is a string that can be on the following form:
                                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                                - v0.12.x - get the highest v0.12 version
                                - v1.x.x - get the highest v1 version
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

    # resolve into both dict and uri form
    if isinstance(dict_or_uri, basestring):
        descriptor_dict = IODescriptorBase.dict_from_uri(dict_or_uri)
    else:
        # make a copy to make sure the original object is never altered
        descriptor_dict = copy.deepcopy(dict_or_uri)

    # at this point we didn't have a cache hit,
    # so construct the object manually
    if resolve_latest:
        # if someone is requesting a latest descriptor and not providing a version token
        # make sure to add an artificial one so that we can resolve it.
        #
        # We only do this for descriptor types that supports a version number concept
        descriptors_using_version = ["app_store", "shotgun", "manual", "git", "git_branch"]

        if "version" not in descriptor_dict and descriptor_dict.get("type") in descriptors_using_version:
            # for the case of latest version, make sure we attach a version
            # key as part of the descriptor dictionary so that the descriptor
            # is valid
            descriptor_dict["version"] = "latest"

    # factory logic
    if descriptor_dict.get("type") == "app_store":
        descriptor = IODescriptorAppStore(descriptor_dict, sg, descriptor_type)

    elif descriptor_dict.get("type") == "shotgun":
        descriptor = IODescriptorShotgunEntity(descriptor_dict, sg)

    elif descriptor_dict.get("type") == "manual":
        descriptor = IODescriptorManual(descriptor_dict, descriptor_type)

    elif descriptor_dict.get("type") == "git":
        descriptor = IODescriptorGitTag(descriptor_dict, descriptor_type)

    elif descriptor_dict.get("type") == "git_branch":
        descriptor = IODescriptorGitBranch(descriptor_dict)

    elif descriptor_dict.get("type") == "dev":
        descriptor = IODescriptorDev(descriptor_dict)

    elif descriptor_dict.get("type") == "path":
        descriptor = IODescriptorPath(descriptor_dict)

    else:
        raise TankDescriptorError("Unknown descriptor type for '%s'" % descriptor_dict)

    # specify where to go look for caches
    descriptor.set_cache_roots(bundle_cache_root, fallback_roots)

    if resolve_latest:
        # attempt to get "remote" latest first
        # and if that fails, fall back on the latest item
        # available in the local cache.
        log.debug("Trying to resolve latest version...")
        if descriptor.has_remote_access():
            log.debug("Remote connection is available - attempting to get latest version from remote...")
            descriptor = descriptor.get_latest_version(constraint_pattern)
        else:
            log.debug("Remote connection is not available - falling back on getting latest version from cache...")
            latest_cached_descriptor = descriptor.get_latest_cached_version(constraint_pattern)
            if latest_cached_descriptor is None:
                raise TankDescriptorError("No cached versions of %r cached locally on disk." % descriptor)

            log.debug("Latest cached descriptor is %r" % latest_cached_descriptor)
            descriptor = latest_cached_descriptor

        log.debug("Resolved latest to be %r" % descriptor)

    return descriptor


def descriptor_uri_to_dict(uri):
    """
    Translates a descriptor uri into a dictionary.

    :param uri: descriptor string uri
    :returns: descriptor dictionary
    """
    from .base import IODescriptorBase
    return IODescriptorBase.dict_from_uri(uri)


def descriptor_dict_to_uri(ddict):
    """
    Translates a descriptor dictionary into a uri.

    :param ddict: descriptor dictionary
    :returns: descriptor uri
    """
    from .base import IODescriptorBase
    return IODescriptorBase.uri_from_dict(ddict)
