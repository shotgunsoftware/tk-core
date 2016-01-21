# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Functionality for managing versions of apps.
"""

import os
import sys
import copy
import sys

from tank_vendor import yaml

from .. import hook
from ..util import shotgun, yaml_cache
from ..errors import TankError, TankFileDoesNotExistError
from ..platform import constants


class VersionedSingletonDescriptor(AppDescriptor):
    """
    Singleton base class for the versioned app descriptor classes.

    Each descriptor object is a singleton based on its install root path,
    name, and version number.
    """
    _instances = dict()

    def __new__(cls, bundle_install_path, location_dict, *args, **kwargs):
        """
        Executed prior to all __init__s. Handles singleton caching of descriptors.

        Since all our normal descriptors are immutable - they represent a specific,
        readonly and cached version of an app, engine or framework on disk, we can
        also cache their wrapper objects.

        All descriptor types deriving from this caching class need to have a
        required name and version key as part of their location dict. These
        keys are used by the class to uniquely identify objects.

        :param bundle_install_path: Location on disk where items are cached
        :param location_dict: Location dictionary describing the bundle
        :return: Descriptor instance
        """

        # We will cache based on the bundle install path, name of the
        # app/engine/framework, and version number.
        instance_cache = cls._instances
        name = location_dict.get("name")
        version = location_dict.get("version")

        if name is None or version is None:
            raise TankError("Cannot process location '%s'. Name and version keys required." % location_dict)

        # Instantiate and cache if we need to, otherwise just return what we
        # already have stored away.
        if (bundle_install_path not in instance_cache or
            name not in instance_cache[bundle_install_path] or
            version not in instance_cache[bundle_install_path][name]):
            # If the bundle install path isn't in the cache, then we are
            # starting fresh. Otherwise, check to see if the app (by name)
            # is cached, and if not initialize its specific cache. After
            # that we instantiate and store by version.
            if bundle_install_path not in instance_cache:
                instance_cache[bundle_install_path] = dict()
            if name not in instance_cache[bundle_install_path]:
                instance_cache[bundle_install_path][name] = dict()
            instance_cache[bundle_install_path][name][version] = super(VersionedSingletonDescriptor, cls).__new__(
                cls,
                bundle_install_path,
                location_dict,
                *args, **kwargs
            )

        return instance_cache[bundle_install_path][name][version]


