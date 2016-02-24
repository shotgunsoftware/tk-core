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
from ..errors import ShotgunDeployError

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

    def __init__(self, location_dict):
        """
        Constructor

        :param location_dict: Location dictionary describing the bundle
        :return: Descriptor instance
        """
        super(IODescriptorDev, self).__init__(location_dict)

    @classmethod
    def dict_from_uri(cls, uri):
        """
        Given a location uri, return a location dict

        :param uri: Location uri string
        :return: Location dictionary
        """
        # sgtk:dev:[name]:local_path
        # sgtk:dev3:[name]:win_path:linux_path:mac_path
        #
        # Examples:
        # sgtk:dev:my-app:/tmp/foo/bar
        # sgtk:dev3::c%3A%0Coo%08ar:/tmp/foo/bar:

        # explode into dictionary
        location_dict = None
        try:
            location_dict = cls._explode_uri(
                uri,
                "dev",
                ["name", "path"]
            )
        except ShotgunDeployError:
            # probably because it's a dev3, not a dev
            pass

        try:
            location_dict = cls._explode_uri(
                uri,
                "dev3",
                ["name", "windows_path", "linux_path", "mac_path"]
            )
            # force set to 'dev', not 'dev3'
            location_dict["type"] = "dev"

        except ShotgunDeployError:
            pass

        if location_dict is None:
            raise ShotgunDeployError("Invalid dev descriptor uri '%s'" % uri)

        # validate it
        cls._validate_locator(
            location_dict,
            required=["type"],
            optional=["name", "linux_path", "mac_path", "path", "windows_path"]
        )
        return location_dict

    @classmethod
    def uri_from_dict(cls, location_dict):
        """
        Given a location dictionary, return a location uri

        :param location_dict: Location dictionary
        :return: Location uri string
        """
        # sgtk:dev:[name]:local_path
        # sgtk:dev3:[name]:win_path:linux_path:mac_path
        #
        # Examples:
        # sgtk:dev:my-app:/tmp/foo/bar
        # sgtk:dev3::c%3A%0Coo%08ar:/tmp/foo/bar:

        cls._validate_locator(
            location_dict,
            required=["type"],
            optional=["name", "version", "linux_path", "mac_path", "path", "windows_path"]
        )

        if "path" in location_dict:
            # single dev style locator takes precedence so as soon as we
            # have a path key, generate the 'path' descriptor rather than a path3.
            return "sgtk:dev:%s:%s" % (
                location_dict.get("name") or "",
                location_dict.get("path")
            )

        else:
            # this is a dev type URI with paths for windows, linux, mac
            return "sgtk:dev3:%s:%s:%s:%s" % (
                location_dict.get("name") or "",
                location_dict.get("windows_path") or "",
                location_dict.get("linux_path") or "",
                location_dict.get("mac_path") or "",
            )

    def is_developer(self):
        """
        Returns true if this item is intended for development purposes
        """
        return True

