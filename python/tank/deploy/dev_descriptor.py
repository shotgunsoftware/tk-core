"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Descriptor that let's you work with local, unversioned files.
This is handy when doing development.

"""

import os
import sys

from ..errors import TankError
from .descriptor import AppDescriptor

class TankDevDescriptor(AppDescriptor):
    """
    Represents a local item. This item is never downloaded
    into the local storage, you interact with it directly.
    """

    def __init__(self, project_root, location_dict):
        super(TankDevDescriptor, self).__init__(project_root, location_dict)

        # platform specific location support
        system = sys.platform
        platform_keys = {"linux2": "linux_path", "darwin": "mac_path", "win32": "windows_path"}
        platform_key = platform_keys.get(system)

        if platform_key not in location_dict and "path" in location_dict:
            self._path = location_dict.get("path", "")
        elif platform_key:
            self._path = location_dict.get(platform_key, "")
        else:
            raise TankError("Platform '%s' is not supported." % system)

        # lastly, resolve environment variables
        self._path = os.path.expandvars(self._path)

        # if there is a version defined in the location dict
        # (this is handy when doing framework development, but totally
        #  non-required for finding the code) 
        self._version = "Undefined"
        if "version" in location_dict:
            self._version = location_dict.get("version")

    @classmethod
    def from_path(cls, project_root, path):
        """
        Factory method which returns an object based on a path
        """
        location_dict = {"type": "dev", "path": path}
        return TankDevDescriptor(project_root, location_dict)

    def get_system_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk
        """
        # use folder name
        bn = os.path.basename(self._path)
        (name, ext) = os.path.splitext(bn)
        return name

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

    def exists_local(self):
        """
        Returns true if this item exists in a local repo
        """
        return os.path.exists(self._path)

    def download_local(self):
        """
        Retrieves this version to local repo
        """
        # do nothing!

    def find_latest_version(self):
        """
        Returns a descriptor object that represents the latest version
        """
        # we are always the latest version :)
        return self

    def install_hook(self, logger, default_hook_name):
        """
        Returns None - dev descriptor doesn't use install or update.
        """
        return


