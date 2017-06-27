# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import with_statement


from .path import IODescriptorPath
from ... import LogManager


log = LogManager.get_logger(__name__)


class IODescriptorInstalledConfig(IODescriptorPath):
    """
    Installed descriptor type is a special type of io_descriptor that can only be used for installed
    configurations and the InstalledConfigurationDescriptor. Its role is to differentiate
    how the configuration folder is packaged inside a standard config descriptor and the installed
    config descriptor. Functionally it operates exactly like a path descriptor, except that it
    doesn't support copying itself.
    """

    def __init__(self, descriptor_dict):
        """
        :param dict descriptor_dict: Dictionary form of the descriptor.
        """
        super(IODescriptorInstalledConfig, self).__init__(descriptor_dict)
