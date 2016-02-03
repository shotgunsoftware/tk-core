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

class IODescriptorPath(IODescriptorBase):
    """
    Represents a local item. This item is never downloaded
    into the local storage, you interact with it directly.

    # location: {"type": "path", "path": "/path/to/app"}

    name is optional and if not specified will be determined based on folder path.
    In the case above, the name would be 'app'
    In the case below, the name would be 'my-app'
    """
    
    def __init__(self, bundle_install_path, location_dict):
        """
        Constructor

        :param bundle_install_path: Location on disk where items are cached
        :param location_dict: Location dictionary describing the bundle
        :return: Descriptor instance
        """

        super(IODescriptorDev, self).__init__(bundle_install_path, location_dict)

        # platform specific location support
        system = sys.platform
        platform_keys = {"linux2": "linux_path", "darwin": "mac_path", "win32": "windows_path"}
        platform_key = platform_keys.get(system, "unsupported_os")

        if platform_key not in location_dict and "path" in location_dict:
            self._path = location_dict.get("path", "")
        elif platform_key and platform_key in location_dict:
            self._path = location_dict.get(platform_key, "")
        else:
            raise ShotgunDeployError(
                    "Invalid descriptor! Could not find a path or a %s entry in the "
                    "location dict %s." % (platform_key, location_dict)
            )

        # lastly, resolve environment variables
        self._path = os.path.expandvars(self._path)
        
        # and normalise:
        self._path = os.path.normpath(self._path)
        
        # if there is a version defined in the location dict
        # (this is handy when doing framework development, but totally
        #  non-required for finding the code) 
        self._version = "Undefined"
        if "version" in location_dict:
            self._version = location_dict.get("version")
            
        # if there is a name defined in the location dict then lets use 
        # this, otherwise we'll fall back to the folder name:
        self._name = location_dict.get("name")
        if not self._name:
            # fall back to the folder name
            bn = os.path.basename(self._path)
            self._name, _ = os.path.splitext(bn)

    def get_system_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk
        """
        return self._name

    def get_version(self):
        """
        Returns the version number string for this item
        """
        return self._version

    def get_path(self):
        """
        returns the path to the folder where this item resides
        """
        return self._path

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

    def find_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.
        
        :param constraint_pattern: If this is specified, the query will be constrained
        by the given pattern. Version patterns are on the following forms:
        
            - v1.2.3 (means the descriptor returned will inevitably be same as self)
            - v1.2.x 
            - v1.x.x

        :returns: descriptor object
        """
        # we are always the latest version :)
        return self


