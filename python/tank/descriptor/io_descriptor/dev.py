# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import subprocess

from .path import IODescriptorPath

from ... import util
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
        super(IODescriptorDev, self).__init__(
            descriptor_dict, sg_connection, bundle_type
        )

    def is_dev(self):
        """
        Returns true if this item is intended for development purposes
        """
        return True

    def get_version(self):
        v = super().get_version()
        print("DEV version:", v)
        if v != "Undefined": # TODO constant
            return v

        rev_hash = self.get_git_output("rev-parse --short HEAD")
        if not rev_hash:
            return v

        return f"Dev {rev_hash}"


    def get_git_output(self, cmd):
        try:
            output = process._check_output(
                f'git -C "{self._path}" {cmd}',
                shell=True,
            )

            # note: it seems on windows, the result is sometimes wrapped in single quotes.
            return output.strip().strip("'")

        except process.SubprocessCalledProcessError as e:
            log.debug("Unable to run git command - {e}")


def _can_hide_terminal():
    """
    Ensures this version of Python can hide the terminal of a subprocess
    launched with the subprocess module.
    """
    try:
        # These values are not defined between Python 2.6.6 and 2.7.1 inclusively.
        subprocess.STARTF_USESHOWWINDOW
        subprocess.SW_HIDE
        return True
    except Exception:
        return False

def _check_output(*args, **kwargs):
    """
    Wraps the call to subprocess_check_output so it can run headless on Windows.
    """
    if util.is_windows() and _can_hide_terminal():
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = startupinfo

    return process.subprocess_check_output(*args, **kwargs)
