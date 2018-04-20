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

from ..util import filesystem
from .io_descriptor import create_io_descriptor
from .errors import TankDescriptorError
from ..util import LocalFileStorageManager
from . import constants

from .descriptor_bundle import AppDescriptor, EngineDescriptor, FrameworkDescriptor
from .descriptor_cached_config import CachedConfigDescriptor
from .descriptor_installed_config import InstalledConfigDescriptor
from .descriptor_core import CoreDescriptor
from .descriptor import Descriptor

from ..log import LogManager

logger = LogManager.get_logger(__name__)


def create_descriptor(
        sg_connection,
        descriptor_type,
        dict_or_uri,
        bundle_cache_root_override=None,
        fallback_roots=None,
        resolve_latest=False,
        constraint_pattern=None,
        local_fallback_when_disconnected=True):
    """
    Factory method. Use this when creating descriptor objects.

    .. note:: Descriptors inherit their threading characteristics from
        the shotgun connection that they carry internally. They are reentrant
        and should not be passed between threads.

    :param sg_connection: Shotgun connection to associated site
    :param descriptor_type: Either ``Descriptor.APP``, ``CORE``, ``CONFIG``, ``INSTALLED_CONFIG``,
        ``ENGINE`` or ``FRAMEWORK``
    :param dict_or_uri: A std descriptor dictionary dictionary or string
    :param bundle_cache_root_override: Optional override for root path to where
                                       downloaded apps are cached. If not specified,
                                       the global bundle cache location will be used. This location is a per-user
                                       cache that is shared across all sites and projects.
    :param fallback_roots: Optional List of immutable fallback cache locations where
                           apps will be searched for. Note that when descriptors
                           download new content, it always ends up in the
                           bundle_cache_root.
    :param resolve_latest: If true, the latest version will be determined and returned.

                           If set to True, no version information needs to be supplied with
                           the descriptor dictionary/uri for descriptor types which support
                           a version number concept. Please note that setting this flag
                           to true will typically affect performance - an external connection
                           is often required in order to establish what the latest version is.

                           If a remote connection cannot be established when attempting to determine
                           the latest version, a local scan will be carried out and the highest
                           version number that is cached locally will be returned.
    :param constraint_pattern: If resolve_latest is True, this pattern can be used to constrain
                           the search for latest to only take part over a subset of versions.
                           This is a string that can be on the following form:

                                - ``v0.1.2``, ``v0.12.3.2``, ``v0.1.3beta`` - a specific version
                                - ``v0.12.x`` - get the highest v0.12 version
                                - ``v1.x.x`` - get the highest v1 version
    :param local_fallback_when_disconnected: If resolve_latest is set to True, specify the behaviour
                            in the case when no connection to a remote descriptor can be established,
                            for example because and internet connection isn't available. If True, the
                            descriptor factory will attempt to fall back on any existing locally cached
                            bundles and return the latest one available. If False, a
                            :class:`TankDescriptorError` is raised instead.

    :returns: :class:`Descriptor` object
    :raises: :class:`TankDescriptorError`
    """
    # use the environment variable if set - if not, fall back on the override or default locations
    if os.environ.get(constants.BUNDLE_CACHE_PATH_ENV_VAR):
        bundle_cache_root_override = os.path.expanduser(
            os.path.expandvars(os.environ.get(constants.BUNDLE_CACHE_PATH_ENV_VAR))
        )
    elif bundle_cache_root_override is None:
        bundle_cache_root_override = _get_default_bundle_cache_root()
        filesystem.ensure_folder_exists(bundle_cache_root_override)
    else:
        # expand environment variables
        bundle_cache_root_override = os.path.expanduser(os.path.expandvars(bundle_cache_root_override))

    fallback_roots = fallback_roots or []

    # expand environment variables
    fallback_roots = [os.path.expandvars(os.path.expanduser(x)) for x in fallback_roots]

    # first construct a low level IO descriptor
    io_descriptor = create_io_descriptor(
        sg_connection,
        descriptor_type,
        dict_or_uri,
        bundle_cache_root_override,
        fallback_roots,
        resolve_latest,
        constraint_pattern,
        local_fallback_when_disconnected
    )

    # now create a high level descriptor and bind that with the low level descriptor
    if descriptor_type == Descriptor.APP:
        return AppDescriptor(sg_connection, io_descriptor)

    elif descriptor_type == Descriptor.ENGINE:
        return EngineDescriptor(sg_connection, io_descriptor)

    elif descriptor_type == Descriptor.FRAMEWORK:
        return FrameworkDescriptor(sg_connection, io_descriptor)

    elif descriptor_type == Descriptor.CONFIG:
        return CachedConfigDescriptor(
            sg_connection, bundle_cache_root_override, fallback_roots, io_descriptor
        )

    elif descriptor_type == Descriptor.INSTALLED_CONFIG:
        return InstalledConfigDescriptor(
            sg_connection, bundle_cache_root_override, fallback_roots, io_descriptor
        )

    elif descriptor_type == Descriptor.CORE:
        return CoreDescriptor(io_descriptor)
    else:
        raise TankDescriptorError("Unsupported descriptor type %s" % descriptor_type)


def _get_default_bundle_cache_root():
    """
    Returns the cache location for the default bundle cache.

    :returns: path on disk
    """
    return os.path.join(
        LocalFileStorageManager.get_global_root(LocalFileStorageManager.CACHE),
        "bundle_cache"
    )

