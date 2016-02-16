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

from .. import util
log = util.get_shotgun_deploy_logger()

class IODescriptorDev(IODescriptorPath):
    """
    Represents a local dev item. This item is never downloaded
    into the local storage, you interact with it directly::

        {"type": "dev", "path": "/path/to/app"}

    Optional parameters are possible::

        {"type": "dev", "path": "/path/to/app", "name": "my-app"}

        {"type": "dev",
         "linux_path": "/path/to/app",
         "windows_path": "d:\foo\bar",
         "mac_path": "/path/to/app" }

    String urls are on the following form::

        sgtk:dev:[name]:local_path
        sgtk:dev3:[name]:win_path:linux_path:mac_path

        sgtk:dev:my-app:/tmp/foo/bar
        sgtk:dev3::c%3A%0Coo%08ar:/tmp/foo/bar:

    Name is optional and if not specified will be determined based on folder path.
    If name is not specified and path is /tmp/foo/bar, the name will set to 'bar'
    """

    def __init__(self, bundle_cache_root, location_dict):
        """
        Constructor

        :param bundle_cache_root: Location on disk where items are cached
        :param location_dict: Location dictionary describing the bundle
        :return: Descriptor instance
        """
        super(IODescriptorDev, self).__init__(bundle_cache_root, location_dict)

    def is_developer(self):
        """
        Returns true if this item is intended for development purposes
        """
        return True

