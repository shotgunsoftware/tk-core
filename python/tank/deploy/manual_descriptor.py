# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Descriptor for manual 

"""

import os

from ..platform import constants
from .descriptor import AppDescriptor

class TankManualDescriptor(AppDescriptor):
    """
    Represents a manually installed item
    """

    def __init__(self, pc_path, bundle_install_path, location_dict, bundle_type):
        super(TankManualDescriptor, self).__init__(pc_path, bundle_install_path, location_dict)
        self._type = bundle_type
        self._name = location_dict.get("name")
        self._version = location_dict.get("version")

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
        return self._get_local_location(self._type, "manual", self._name, self._version)

    def exists_local(self):
        """
        Returns true if this item exists in a local repo
        """
        # we determine local existance based on the info.yml
        info_yml_path = os.path.join(self.get_path(), constants.BUNDLE_METADATA_FILE)
        return os.path.exists(info_yml_path)

    def download_local(self):
        """
        Retrieves this version to local repo
        """
        # do nothing!

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
        # since this descriptor has no way of updating and no way of knowing 
        # what is latest, just return our own version as representing the latest version.
        return self



