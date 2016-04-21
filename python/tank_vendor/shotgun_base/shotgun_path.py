# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sys
from .utils import sanitize_path


class ShotgunPath(object):
    """
    Helper class that handles a path on multiple operating systems.

    Contains methods to easily cast multi-os path between shotgun and os representations
    and mappings.

    The ShotgunPath object automatically sanitizes any path that it is given.

    Usage example::

        >>> ShotgunPath.SHOTGUN_PATH_FIELDS
        ["windows_path", "linux_path", "mac_path"]

        >>> p = ShotgunPath("C:\temp", "/tmp", "/tmp")

        >>> p = ShotgunPath.from_shotgun_dict({ "windows_path": "C:\temp", "mac_path": None, "linux_path": "/tmp"})

        >>> p = ShotgunPath.from_system_dict({ "win32": "C:\temp", "darwin": None, "linux2": "/tmp"})

        >>> p = ShotgunPath.from_current_os_path("/tmp")

        >>> p.mac
        '/tmp'

        >>> p.windows
        "C:\\temp"

        >>> p.linux
        '/tmp

        >>> p.current_os
        '/tmp'

        >>> p.as_shotgun_dict()
        { "windows_path": "C:\temp", "mac_path": None, "linux_path": "/tmp"}

        >>> p2 = p.join('foo')
        >>> p2
        <Path win:'c:\temp\foo', linux:'/tmp/foo', mac:'/tmp/foo'>

    """

    SHOTGUN_PATH_FIELDS = ["windows_path", "linux_path", "mac_path"]
    """
    Returns a list of the standard path fields used by Shotgun.
    """

    @classmethod
    def from_shotgun_dict(cls, sg_dict):
        """
        Creates a path from data contained in a std shotgun data dict,
        containing the paths windows_path, mac_path and linux_path

        :param sg_dict: Shotgun query resultset with possible keys
                        windows_path, mac_path and linux_path.
        :return: ShotgunPath instance
        """
        windows_path = sg_dict.get("windows_path")
        linux_path = sg_dict.get("linux_path")
        macosx_path = sg_dict.get("mac_path")
        return cls(windows_path, linux_path, macosx_path)

    @classmethod
    def from_system_dict(cls, system_dict):
        """
        Creates a path from data contained in a dictionary keyed by
        sys.platform constants.

        :param system_dict: Dictionary with possible keys
                        win32, darwin and linux2.
        :return: ShotgunPath instance
        """
        windows_path = system_dict.get("win32")
        linux_path = system_dict.get("linux2")
        macosx_path = system_dict.get("darwin")

        return cls(windows_path, linux_path, macosx_path)

    @classmethod
    def from_current_os_path(cls, path):
        """
        Creates a path object for a path on the current platform only.

        :param path: Path on the current os platform.
        :return: ShotgunPath instance
        """
        windows_path = None
        linux_path = None
        macosx_path = None

        if sys.platform == "win32":
            windows_path = path
        elif sys.platform == "linux2":
            linux_path = path
        elif sys.platform == "darwin":
            macosx_path = path
        else:
            return ValueError("Unsupported platform '%s'." % sys.platform)

        return cls(windows_path, linux_path, macosx_path)

    def __init__(self, windows_path=None, linux_path=None, macosx_path=None):
        """
        Constructor

        :param windows_path: Path on windows to associate with this path object
        :param linux_path: Path on linux to associate with this path object
        :param macosx_path: Path on mac to associate with this path object
        """
        self._windows_path = sanitize_path(windows_path, "\\")
        self._linux_path = sanitize_path(linux_path, "/")
        self._macosx_path = sanitize_path(macosx_path, "/")

    def __repr__(self):
        return "<Path win:'%s', linux:'%s', mac:'%s'>" % (
            self._windows_path,
            self._linux_path,
            self._macosx_path
        )

    def __eq__(self, other):
        """
        Test if this ShotgunPath instance is equal to the other ShotgunPath instance

        :param other:   The other ShotgunPath instance to compare with
        :returns:       True if path is same is other, false otherwise
        """

        if not isinstance(other, ShotgunPath):
            return NotImplemented

        return self.mac == other.mac and self.windows == other.windows and self.linux == other.linux

    def __ne__(self, other):
        """
        Test if this path is not equal to the given path

        :param other:   Other ShotgunPath instance to compare with
        :returns:       True if self != other, False otherwise
        """
        is_equal = self.__eq__(other)
        if is_equal is NotImplemented:
            return NotImplemented
        return not is_equal

    @property
    def mac(self):
        """
        The macosx representation of the path
        """
        return self._macosx_path

    @property
    def windows(self):
        """
        The macosx representation of the path
        """
        return self._windows_path

    @property
    def linux(self):
        """
        The macosx representation of the path
        """
        return self._linux_path

    @property
    def current_os(self):
        """
        The path on the current os
        """
        if sys.platform == "win32":
            return self.windows
        elif sys.platform == "linux2":
            return self.linux
        elif sys.platform == "darwin":
            return self.mac
        else:
            return ValueError("Unsupported platform '%s'." % sys.platform)

    def as_shotgun_dict(self, include_empty=True):
        """
        The path as a shotgun dictionary. With include_empty set to True:

            { "windows_path": "C:\\temp", "mac_path": None, "linux_path": "/tmp"}

        With include_empty set to False:

            { "windows_path": "C:\\temp", "linux_path": "/tmp"}

        :param include_empty: Controls whether keys should be included for empty path values
        :return: dictionary of paths keyed by standard shotgun keys.
        """
        d = {}
        if self._windows_path or include_empty:
            d["windows_path"] = self._windows_path
        if self._macosx_path or include_empty:
            d["mac_path"] = self._macosx_path
        if self._linux_path or include_empty:
            d["linux_path"] = self._linux_path
        return d

    def join(self, folder):
        """
        Appends a single folder to the path

        :param folder: folder name as sting
        :returns: ShotgunPath object containing the new path
        """
        # get rid of any slashes at the end
        # so value is "/foo/bar", "c:" or "\\hello"
        # then append separator and new folder
        linux_path = "%s/%s" % (self._linux_path.rstrip("/\\"), folder) if self._linux_path else None
        mac_path = "%s/%s" % (self._macosx_path.rstrip("/\\"), folder) if self._macosx_path else None
        win_path = "%s\\%s" % (self._windows_path.rstrip("/\\"), folder) if self._windows_path else None

        return ShotgunPath(win_path, linux_path, mac_path)
