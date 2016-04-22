# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import tempfile

from tank_test.tank_test_base import *



class TestIODescriptors(TankTestBase):
    """
    Testing the Shotgun deploy main API methods
    """

    def test_descriptor_cache(self):
        """
        Tests caching of descriptors
        """
        sg = self.tk.shotgun

        location1 = {"type": "app_store", "version": "v1.1.1", "name": "tk-bundle"}
        location2 = {"type": "app_store", "version": "v3.3.3", "name": "tk-bundle"}

        d1 = shotgun_deploy.create_descriptor(sg, shotgun_deploy.Descriptor.APP, location1)
        d2 = shotgun_deploy.create_descriptor(sg, shotgun_deploy.Descriptor.APP, location1)
        d3 = shotgun_deploy.create_descriptor(sg, shotgun_deploy.Descriptor.APP, location2)

        # note that we don't use the equality operator here but using 'is' to
        # make sure we are getting the same instance back
        self.assertTrue(d1._io_descriptor is d2._io_descriptor)
        self.assertTrue(d1._io_descriptor is not d3._io_descriptor)
