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
import sgtk


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

        d1 = sgtk.descriptor.create_descriptor(sg, sgtk.descriptor.Descriptor.APP, location1)
        d2 = sgtk.descriptor.create_descriptor(sg, sgtk.descriptor.Descriptor.APP, location1)
        d3 = sgtk.descriptor.create_descriptor(sg, sgtk.descriptor.Descriptor.APP, location2)

        # note that we don't use the equality operator here but using 'is' to
        # make sure we are getting the same instance back
        self.assertTrue(d1._io_descriptor is d2._io_descriptor)
        self.assertTrue(d1._io_descriptor is not d3._io_descriptor)


    def test_cache_locations(self):
        """
        Tests locations of caches when using fallback paths.
        """
        sg = self.tk.shotgun

        root_a = os.path.join(self.project_root, "cache_root_a")
        root_b = os.path.join(self.project_root, "cache_root_b")
        root_c = os.path.join(self.project_root, "cache_root_c")
        root_d = os.path.join(self.project_root, "cache_root_d")


        location = {"type": "app_store", "version": "v1.1.1", "name": "tk-bundle"}


        d = sgtk.descriptor.create_descriptor(
            sg,
            sgtk.descriptor.Descriptor.APP,
            location,
            bundle_cache_root_override=root_a,
            fallback_roots=[root_b, root_c, root_d]
        )

        self.assertEqual(
            d._io_descriptor._get_primary_cache_path(),
            os.path.join(root_a, "app_store", "tk-bundle", "v1.1.1")
        )

        self.assertEqual(
            d._io_descriptor._get_cache_paths(),
            [
                os.path.join(root_b, "app_store", "tk-bundle", "v1.1.1"),
                os.path.join(root_c, "app_store", "tk-bundle", "v1.1.1"),
                os.path.join(root_d, "app_store", "tk-bundle", "v1.1.1"),
                os.path.join(root_a, "app_store", "tk-bundle", "v1.1.1"),
                os.path.join(root_a, "apps", "app_store", "tk-bundle", "v1.1.1") # legacy path
            ]
        )

