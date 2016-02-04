# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.


from .path import IODescriptorPath

class IODescriptorDev(IODescriptorPath):
    """
    Represents a local dev item. This item is never downloaded
    into the local storage, you interact with it directly.

    # location: {"type": "dev", "path": "/path/to/app"}

    name is optional and if not specified will be determined based on folder path.
    In the case above, the name would be 'app'
    In the case below, the name would be 'my-app'

    # location: {"type": "dev", "path": "/path/to/app", name: "my-app"}

    """
    
    def __init__(self, bundle_cache_root, location_dict):
        """
        Constructor

        :param bundle_cache_root: Location on disk where items are cached
        :param location_dict: Location dictionary describing the bundle
        :return: Descriptor instance
        """

        super(IODescriptorPath, self).__init__(bundle_cache_root, location_dict)

    def is_developer(self):
        """
        Returns true if this item is intended for development purposes
        """
        return True

