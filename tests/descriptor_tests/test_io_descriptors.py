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

    def test_latest_cached(self):
        """
        Tests the find_latest_cached_version method
        """
        sg = self.tk.shotgun
        root = os.path.join(self.project_root, "cache_root")

        d = sgtk.descriptor.create_descriptor(
            sg,
            sgtk.descriptor.Descriptor.APP,
            {"type": "app_store", "version": "v1.1.1", "name": "tk-bundle"},
            bundle_cache_root_override=root
        )

        d2 = sgtk.descriptor.create_descriptor(
            sg,
            sgtk.descriptor.Descriptor.APP,
            {"type": "app_store", "version": "v1.2.1", "name": "tk-bundle"},
            bundle_cache_root_override=root
        )

        d3 = sgtk.descriptor.create_descriptor(
            sg,
            sgtk.descriptor.Descriptor.APP,
            {"type": "app_store", "version": "v1.3.1", "name": "tk-bundle"},
            bundle_cache_root_override=root
        )

        self.assertEqual(d.get_path(), None)
        self.assertEqual(d.find_latest_cached_version(), None)

        app_path = os.path.join(root, "app_store", "tk-bundle", "v1.1.1")
        path = os.path.join(app_path, "info.yml")

        os.makedirs(app_path)
        fh = open(path, "wt")
        fh.write("test data\n")
        fh.close()

        self.assertEqual(d.get_path(), app_path)
        self.assertEqual(d.find_latest_cached_version(), d)



        self.assertEqual(d2.get_path(), None)

        app_path = os.path.join(root, "app_store", "tk-bundle", "v1.2.1")
        path = os.path.join(app_path, "info.yml")
        os.makedirs(app_path)
        fh = open(path, "wt")
        fh.write("test data\n")
        fh.close()

        self.assertEqual(d2.get_path(), app_path)
        self.assertEqual(d.find_latest_cached_version(), d2)

        # Check to make sure we find a bundle that doesn't have an info.yml.
        app_path = os.path.join(root, "app_store", "tk-bundle", "v1.3.1")
        os.makedirs(app_path)

        self.assertEqual(d3.get_path(), app_path)
        self.assertEqual(d.find_latest_cached_version(), d3)

        # now check constraints
        self.assertEqual(d.find_latest_cached_version("v1.1.x"), d)
        self.assertEqual(d.find_latest_cached_version("v1.2.x"), d2)
        self.assertEqual(d.find_latest_cached_version("v1.x.x"), d3)
        self.assertEqual(d.find_latest_cached_version("v2.x.x"), None)


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

