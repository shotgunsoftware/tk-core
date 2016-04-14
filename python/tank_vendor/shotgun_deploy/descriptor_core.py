# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

from .descriptor import Descriptor
from . import constants

class CoreDescriptor(Descriptor):
    """
    Descriptor object which describes a Toolkit Core API version.
    """

    def __init__(self, io_descriptor):
        """
        Constructor

        :param io_descriptor: Associated IO descriptor.
        """
        super(CoreDescriptor, self).__init__(io_descriptor)

    def get_version_constraints(self):
        """
        Returns a dictionary with version constraints. The absence of a key
        indicates that there is no defined constraint. The following keys can be
        returned: min_sg, min_core, min_engine and min_desktop

        :returns: Dictionary with optional keys min_sg, min_core,
                  min_engine, min_desktop
        """
        constraints = {}

        manifest = self._io_descriptor.get_manifest()

        constraints["min_sg"] = manifest.get("requires_shotgun_version", constants.LOWEST_SHOTGUN_VERSION)

        return constraints
