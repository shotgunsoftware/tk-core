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
import sys

from .base import IODescriptorBase
from ..errors import ShotgunDeployError

from ...shotgun_base import get_shotgun_storage_key

class IODescriptorPath(IODescriptorBase):
    """
    Represents a local item on disk. This item is never downloaded
    into the local storage, you interact with it directly::

        {"type": "path", "path": "/path/to/app"}

    Optional parameters are possible::

        {"type": "path", "path": "/path/to/app", "name": "my-app"}

        {"type": "path",
         "linux_path": "/path/to/app",
         "windows_path": "d:\foo\bar",
         "mac_path": "/path/to/app" }

    Name is optional and if not specified will be determined based on folder path.
    If name is not specified and path is /tmp/foo/bar, the name will set to 'bar'
    """
    
    def __init__(self, descriptor_dict):
        """
        Constructor

        :param descriptor_dict: descriptor dictionary describing the bundle
        :return: Descriptor instance
        """

        super(IODescriptorPath, self).__init__(descriptor_dict)

        self._validate_descriptor(
            descriptor_dict,
            required=["type"],
            optional=["name", "linux_path", "mac_path", "path", "windows_path"]
        )

        # platform specific location support
        platform_key = get_shotgun_storage_key()

        if "path" in descriptor_dict:
            # first look for 'path' key
            self._path = descriptor_dict["path"]
            self._multi_os_descriptor = False
        elif platform_key in descriptor_dict:
            # if not defined, look for os specific key
            self._path = descriptor_dict[platform_key]
            self._multi_os_descriptor = True
        else:
            raise ShotgunDeployError(
                "Invalid descriptor! Could not find a path or a %s entry in the "
                "descriptor dict %s." % (platform_key, descriptor_dict)
            )

        # lastly, resolve environment variables
        self._path = os.path.expandvars(self._path)
        
        # and normalise:
        self._path = os.path.normpath(self._path)
        
        # if there is a name defined in the descriptor dict then lets use
        # this, otherwise we'll fall back to the folder name:
        self._name = descriptor_dict.get("name")
        if not self._name:
            # fall back to the folder name
            bn = os.path.basename(self._path)
            self._name, _ = os.path.splitext(bn)

    def _get_cache_paths(self):
        """
        Get a list of resolved paths, starting with the primary and
        continuing with alternative locations where it may reside.

        Note: This method only computes paths and does not perform any I/O ops.

        :return: List of path strings
        """
        return [self._path]

    def get_system_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk, e.g. 'tk-maya'
        """
        return self._name

    def get_version(self):
        """
        Returns the version number string for this item
        """
        # version number does not make sense for this type of item
        # so a fixed string is returned
        return "v0.0.0"

    def download_local(self):
        """
        Retrieves this version to local repo
        """
        # do nothing!

    def is_immutable(self):
        """
        Returns true if this items content never changes
        """
        return False

    def get_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.

        :param constraint_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:

                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                - v0.12.x - get the highest v0.12 version
                - v1.x.x - get the highest v1 version

        :returns: descriptor object
        """
        # we are always the latest version :)
        return self


