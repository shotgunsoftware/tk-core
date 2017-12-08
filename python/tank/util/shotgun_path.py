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


class ShotgunPath(object):
    """
    Helper class that handles a path on multiple operating systems.

    Contains methods to easily cast multi-os path between shotgun and os representations
    and mappings. The ShotgunPath object automatically sanitizes any path that it is given.
    When working with local storages in Shotgun, roots are keyed by the tokens
    ``windows_path``, ``linux_path`` and ``mac_path``. When using ``sys.platform`` in python,
    you get back ``win32``, ``darwin`` and ``linux2`` depending on platform. This class makes
    it easy to perform operations and cast between representations and platforms.

    Usage example::

        >>> ShotgunPath.SHOTGUN_PATH_FIELDS
        ["windows_path", "linux_path", "mac_path"]

        # construction
        >>> p = ShotgunPath("C:\\temp", "/tmp", "/tmp")
        >>> p = ShotgunPath.from_shotgun_dict({ "windows_path": "C:\\temp", "mac_path": None, "linux_path": "/tmp"})
        >>> p = ShotgunPath.from_system_dict({ "win32": "C:\\temp", "darwin": None, "linux2": "/tmp"})
        >>> p = ShotgunPath.from_current_os_path("/tmp")

        # access
        >>> p.macosx
        None
        >>> p.windows
        "C:\\temp"
        >>> p.linux
        '/tmp
        >>> p.current_os
        '/tmp'

        # multi-platform access
        >>> p.as_shotgun_dict()
        { "windows_path": "C:\\temp", "mac_path": None, "linux_path": "/tmp"}
        >>> p.as_system_dict()
        { "win32": "C:\\temp", "darwin": None, "linux2": "/tmp"}

        # path manipulation
        >>> p2 = p.join('foo')
        >>> p2
        <Path win:'c:\\temp\\foo', linux:'/tmp/foo', macosx:'/tmp/foo'>

    """

    SHOTGUN_PATH_FIELDS = ["windows_path", "linux_path", "mac_path"]
    """
    A list of the standard path fields used by Shotgun.
    """

    @staticmethod
    def get_file_name_from_template(template, platform=sys.platform):
        """
        Returns the complete file name for the current platform based on
        file name template passed in.

        :param str template: Template for a file name with a ``%s`` to indicate
            where the platform name should be inserted.

        :returns: Path with the OS name substituted in.
        """
        if platform == "win32":
            os_name = "Windows"
        elif platform == "darwin":
            os_name = "Darwin"
        elif platform.startswith("linux"):
            os_name = "Linux"
        else:
            raise ValueError(
                "Cannot resolve file name - unsupported "
                "os platform '%s'" % platform
            )
        return template % os_name

    @staticmethod
    def get_shotgun_storage_key(platform=sys.platform):
        """
        Given a ``sys.platform`` constant, resolve a Shotgun storage key

        Shotgun local storages handle operating systems using
        the three keys 'windows_path, 'mac_path' and 'linux_path',
        also defined as ``ShotgunPath.SHOTGUN_PATH_FIELDS``

        This method resolves the right key given a std. python
        sys.platform::


            >>> p.get_shotgun_storage_key('win32')
            'windows_path'

            # if running on a mac
            >>> p.get_shotgun_storage_key()
            'mac_path'

        :param platform: sys.platform style string, e.g 'linux2',
                         'win32' or 'darwin'.
        :returns: Shotgun storage path as string.
        """
        if platform == "win32":
            return "windows_path"
        elif platform == "darwin":
            return "mac_path"
        elif platform.startswith("linux"):
            return "linux_path"
        else:
            raise ValueError(
                "Cannot resolve Shotgun storage - unsupported "
                "os platform '%s'" % platform
            )

    @classmethod
    def from_shotgun_dict(cls, sg_dict):
        """
        Creates a path from data contained in a std shotgun data dict,
        containing the paths windows_path, mac_path and linux_path

        :param sg_dict: Shotgun query resultset with possible keys
                        windows_path, mac_path and linux_path.
        :return: :class:`ShotgunPath` instance
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
        :return: :class:`ShotgunPath` instance
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
        :return: :class:`ShotgunPath` instance
        """
        windows_path = None
        linux_path = None
        macosx_path = None

        if sys.platform == "win32":
            windows_path = path
        elif sys.platform.startswith("linux"):
            linux_path = path
        elif sys.platform == "darwin":
            macosx_path = path
        else:
            raise ValueError("Unsupported platform '%s'." % sys.platform)

        return cls(windows_path, linux_path, macosx_path)

    @classmethod
    def normalize(cls, path):
        """
        Convenience method that normalizes the given path
        by running it through the :class:`ShotgunPath` normalization
        logic. ``ShotgunPath.normalize(path)`` is equivalent
        to executing ``ShotgunPath.from_current_os_path(path).current_os``.

        Normalization include checking that separators are matching the
        current operating system, removal of trailing separators
        and removal of double separators. This is done automatically
        for all :class:`ShotgunPath`s but sometimes it is useful
        to just perform the normalization quickly on a local path.

        :param str path: Local operating system path to normalize
        :return: Normalized path string.
        """
        return cls.from_current_os_path(path).current_os

    def __init__(self, windows_path=None, linux_path=None, macosx_path=None):
        """
        :param windows_path: Path on windows to associate with this path object
        :param linux_path: Path on linux to associate with this path object
        :param macosx_path: Path on macosx to associate with this path object
        """
        self._windows_path = self._sanitize_path(windows_path, "\\")
        self._linux_path = self._sanitize_path(linux_path, "/")
        self._macosx_path = self._sanitize_path(macosx_path, "/")

    def __nonzero__(self):
        """
        Checks if one or more of the OSes have a path specified.

        :returns: True if one or more of the OSes has a path specified. False if all are None.
        """
        # If we're different than an empty path, we're not zero!
        return True if self.windows or self.linux or self.macosx else False

    def __repr__(self):
        return "<Path win:'%s', linux:'%s', macosx:'%s'>" % (
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

        return self.macosx == other.macosx and self.windows == other.windows and self.linux == other.linux

    def __hash__(self):
        """
        Creates an hash from this ShotgunPath.
        """
        return hash((self.macosx, self.windows, self.linux))

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

    def _sanitize_path(self, path, separator):
        """
        Multi-platform sanitize and clean up of paths.

        The following modifications will be carried out:

        None returns None

        Trailing slashes are removed:
        1. /foo/bar      - unchanged
        2. /foo/bar/     - /foo/bar
        3. z:/foo/       - z:\foo
        4. z:/           - z:\
        5. z:\           - z:\
        6. \\foo\bar\    - \\foo\bar

        Double slashes are removed:
        1. //foo//bar    - /foo/bar
        2. \\foo\\bar    - \\foo\bar

        Leading and trailing spaces are removed:
        1. "   Z:\foo  " - "Z:\foo"

        :param path: the path to clean up
        :param separator: the os.sep to adjust the path for. / on nix, \ on win.
        :returns: cleaned up path
        """
        if path is None:
            return None

        # ensure there is no white space around the path
        path = path.strip()

        # get rid of any slashes at the end
        # after this step, path value will be "/foo/bar", "c:" or "\\hello"
        path = path.rstrip("/\\")

        # add slash for drive letters: c: --> c:/
        if len(path) == 2 and path.endswith(":"):
            path += "/"

        # and convert to the right separators
        # after this we have a path with the correct slashes and no end slash
        local_path = path.replace("\\", separator).replace("/", separator)

        # now weed out any duplicated slashes. iterate until done
        while True:
            new_path = local_path.replace("//", "/")
            if new_path == local_path:
                break
            else:
                local_path = new_path

        # for windows, remove duplicated backslashes, except if they are
        # at the beginning of the path
        while True:
            new_path = local_path[0] + local_path[1:].replace("\\\\", "\\")
            if new_path == local_path:
                break
            else:
                local_path = new_path

        return local_path

    def _get_macosx(self):
        """
        The macosx representation of the path
        """
        return self._macosx_path

    def _set_macosx(self, value):
        """
        The macosx representation of the path
        """
        self._macosx_path = self._sanitize_path(value, "/")

    macosx = property(_get_macosx, _set_macosx)

    def _get_windows(self):
        """
        The Windows representation of the path
        """
        return self._windows_path

    def _set_windows(self, value):
        """
        The Windows representation of the path
        """
        self._windows_path = self._sanitize_path(value, "\\")

    windows = property(_get_windows, _set_windows)

    def _get_linux(self):
        """
        The Linux representation of the path
        """
        return self._linux_path

    def _set_linux(self, value):
        """
        The Windows representation of the path
        """
        self._linux_path = self._sanitize_path(value, "/")

    linux = property(_get_linux, _set_linux)

    def _get_current_os(self):
        """
        The path on the current os
        """
        if sys.platform == "win32":
            return self.windows
        elif sys.platform.startswith("linux"):
            return self.linux
        elif sys.platform == "darwin":
            return self.macosx
        else:
            raise ValueError("Unsupported platform '%s'." % sys.platform)

    def _set_current_os(self, value):
        """
        The path on the current os
        """
        # Please note that we're using the property setters to set the path, so they
        # will be sanitized by the setter.
        if sys.platform == "win32":
            self.windows = value
        elif sys.platform.startswith("linux"):
            self.linux = value
        elif sys.platform == "darwin":
            self.macosx = value
        else:
            raise ValueError("Unsupported platform '%s'." % sys.platform)

    current_os = property(_get_current_os, _set_current_os)

    def as_shotgun_dict(self, include_empty=True):
        """
        The path as a shotgun dictionary. With ``include_empty`` set to True::

            { "windows_path": "C:\\temp", "mac_path": None, "linux_path": "/tmp"}

        With ``include_empty`` set to False::

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

    def as_system_dict(self, include_empty=True):
        """
        The path as a dictionary keyed by sys.platform.

        With ``include_empty`` set to True::

            { "win32": "C:\\temp", "darwin": None, "linux2": "/tmp"}

        With ``include_empty`` set to False::

            { "win32": "C:\\temp", "linux2": "/tmp"}

        :param include_empty: Controls whether keys should be included for empty path values
        :return: dictionary of paths keyed by sys.platform.
        """
        d = {}
        if self._windows_path or include_empty:
            d["win32"] = self._windows_path
        if self._macosx_path or include_empty:
            d["darwin"] = self._macosx_path
        if self._linux_path or include_empty:
            d["linux2"] = self._linux_path
        return d

    def join(self, folder):
        """
        Appends a single folder to the path.

        :param folder: folder name as sting
        :returns: :class:`ShotgunPath` object containing the new path
        """
        # get rid of any slashes at the end
        # so value is "/foo/bar", "c:" or "\\hello"
        # then append separator and new folder
        linux_path = "%s/%s" % (self._linux_path.rstrip("/\\"), folder) if self._linux_path else None
        macosx_path = "%s/%s" % (self._macosx_path.rstrip("/\\"), folder) if self._macosx_path else None
        win_path = "%s\\%s" % (self._windows_path.rstrip("/\\"), folder) if self._windows_path else None

        return ShotgunPath(win_path, linux_path, macosx_path)
