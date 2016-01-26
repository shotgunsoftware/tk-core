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

from .descriptor_io import create_io_descriptor

from .descriptor import Descriptor
from .descriptor_bundle import AppDescriptor, EngineDescriptor, FrameworkDescriptor
from .descriptor_config import ConfigDescriptor
from .descriptor_core import CoreDescriptor


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

    # first construct a low level IO descriptor
    io_descriptor = create_io_descriptor(sg_connection, descriptor_type, location_dict, bundle_cache_root)

    # now create a high level descriptor and bind that with the low level descriptor
    if descriptor_type == Descriptor.APP:
        return AppDescriptor(io_descriptor)

    elif descriptor_type == Descriptor.ENGINE:
        return EngineDescriptor(io_descriptor)

    elif descriptor_type == Descriptor.FRAMEWORK:
        return FrameworkDescriptor(io_descriptor)

    elif descriptor_type == Descriptor.CONFIG:
        return ConfigDescriptor(io_descriptor)

    elif descriptor_type == Descriptor.CORE:
        return CoreDescriptor(io_descriptor)

    else:
        raise ShotgunDeployError("%s: Invalid location dict '%s'" % (descriptor_type, location_dict))

