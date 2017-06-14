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

import os
import cgi
import urllib
import urlparse

from .path import IODescriptorPath
from .. import constants
from ... import LogManager
from ...util import filesystem

from ..errors import TankDescriptorError

from tank_vendor import yaml

log = LogManager.get_logger(__name__)


class IODescriptorInstalled(IODescriptorPath):
    """
    Installed descriptor type is a special type of io_descriptor that can only be used for installed
    configurations and the InstalledConfigurationDescriptor. Its role is to differentiate
    how the configuration folder is packaged inside a standard config descriptor and the installed
    config descriptor. Functionally it operates exactly like a path descriptor, except that it
    doesn't support copying itself.
    """

    def copy(self, target_path):
        """
        Copy the contents of the descriptor to an external location

        :param target_path: target path to copy the descriptor to.
        """
        raise TankDescriptorError("Installed descriptor is not copiable.")

    def _get_manifest_location(self):
        return os.path.join(self._path, "config")

    def get_manifest(self):
        """
        Returns the info.yml metadata associated with this descriptor.
        Note that this call involves deep introspection; in order to
        access the metadata we normally need to have the code content
        local, so this method may trigger a remote code fetch if necessary.

        :returns: dictionary with the contents of info.yml
        """
        if self.__manifest_data is None:
            # get the metadata
            bundle_root = self.get_path()
            file_path = os.path.join(bundle_root, "config", constants.BUNDLE_METADATA_FILE)

            if not os.path.exists(file_path):
                # installed descriptors do not always have an info.yml file, so allow an empty dict.
                metadata = {}
            else:
                try:
                    with open(file_path) as fh:
                        metadata = yaml.load(fh)
                except Exception, exp:
                    raise TankDescriptorError("Cannot load metadata file '%s'. Error: %s" % (file_path, exp))

            # cache it
            self.__manifest_data = metadata

        return self.__manifest_data


