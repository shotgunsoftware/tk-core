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

from ...util import process
from ... import LogManager

log = LogManager.get_logger(__name__)


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

    Name is optional and if not specified will be determined based on folder path.
    If name is not specified and path is /tmp/foo/bar, the name will set to 'bar'
    """

    def __init__(self, descriptor_dict, sg_connection, bundle_type):
        """
        Constructor

        :param descriptor_dict: descriptor dictionary describing the bundle
        :param sg_connection: Shotgun connection to associated site.
        :param bundle_type: Either AppDescriptor.APP, CORE, ENGINE or FRAMEWORK.
        :return: Descriptor instance
        """
        super().__init__(descriptor_dict, sg_connection, bundle_type)

    def is_dev(self):
        """
        Returns true if this item is intended for development purposes
        """
        return True

    def get_version(self):
        v = super().get_version()
        if v.lower() != "undefined": # TODO constant
            return v

        desc = self.get_git_output("describe", "--tags", "--first-parent")
        if not desc:
            return v

        return desc.replace("-", "+dev-", 1)

    def get_git_output(self, *args):
        cmd_args = ["git", "-C", self._path]
        cmd_args.extend(args)
        try:
            output = process.subprocess_check_output(cmd_args)
        except process.SubprocessCalledProcessError as e:
            log.debug("Unable to run git command - {e}")
        else:
            # note: it seems on windows, the result is sometimes wrapped in single quotes.
            return output.strip().strip("'")
