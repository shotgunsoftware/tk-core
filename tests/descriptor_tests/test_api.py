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
import uuid
import sgtk

from tank_test.tank_test_base import *



class TestApi(TankTestBase):
    """
    Testing the Shotgun deploy main API methods
    """

    def _touch_info_yaml(self, path):
        """
        Helper method that creates an info.yml dummy
        file in the given location
        """
        sgtk.util.filesystem.ensure_folder_exists(path)
        fh = open(os.path.join(path, "info.yml"), "wt")
        fh.write("# unit test placeholder file\n\n")
        fh.close()


    def test_factory(self):
        """
        Basic test of descriptor construction
        """
        d = sgtk.descriptor.create_descriptor(
            self.tk.shotgun,
            sgtk.descriptor.Descriptor.CONFIG,
            {"type": "app_store", "version": "v0.1.6", "name": "tk-testbundlefactory"}
        )

        app_root_path = os.path.join(
            tank.util.LocalFileStorageManager.get_global_root(tank.util.LocalFileStorageManager.CACHE),
            "bundle_cache",
            "app_store",
            "tk-testbundlefactory",
            "v0.1.6"
        )

        self._touch_info_yaml(app_root_path)
        self.assertEqual(app_root_path, d.get_path())

        d1 = sgtk.descriptor.create_descriptor(
            self.tk.shotgun,
            sgtk.descriptor.Descriptor.CONFIG,
            "sgtk:descriptor:git?path=https%3A//github.com/shotgunsoftware/tk-core.git&version=v0.1.2"
        )

        d2 = sgtk.descriptor.create_descriptor(
            self.tk.shotgun,
            sgtk.descriptor.Descriptor.CONFIG,
            "sgtk:descriptor:git?path=https://github.com/shotgunsoftware/tk-core.git&version=v0.1.2"
        )

        d3 = sgtk.descriptor.create_descriptor(
            self.tk.shotgun,
            sgtk.descriptor.Descriptor.CONFIG,
            {"type": "git", "version": "v0.1.2", "path": "https://github.com/shotgunsoftware/tk-core.git"}
        )

        self.assertEqual(d1, d2)
        self.assertEqual(d2, d3)
        self.assertEqual(d1, d3)

    def test_latest(self):
        """
        Basic test of resolve_latest flag
        """
        # descriptors without version tag are not allowed unless the latest flag is set
        self.assertRaises(
            sgtk.descriptor.TankDescriptorError,
            sgtk.descriptor.create_descriptor,
            self.tk.shotgun,
            sgtk.descriptor.Descriptor.CONFIG,
            {"type": "app_store", "name": "tk-testbundlefactory"}
        )

        # if we omit the version number, a latest check is carried out
        app_root_path = os.path.join(
            tank.util.LocalFileStorageManager.get_global_root(tank.util.LocalFileStorageManager.CACHE),
            "bundle_cache",
            "app_store",
            "tk-testbundlefactory",
            "v0.1.6"
        )
        self._touch_info_yaml(app_root_path)
        d = sgtk.descriptor.create_descriptor(
            self.tk.shotgun,
            sgtk.descriptor.Descriptor.CONFIG,
            {"type": "app_store", "name": "tk-testbundlefactory"},
            resolve_latest=True
        )
        self.assertEqual(d.get_uri(), "sgtk:descriptor:app_store?version=v0.1.6&name=tk-testbundlefactory")

        # if we add a new local version, this will be picked up as latest
        app_root_path = os.path.join(
            tank.util.LocalFileStorageManager.get_global_root(tank.util.LocalFileStorageManager.CACHE),
            "bundle_cache",
            "app_store",
            "tk-testbundlefactory",
            "v0.2.3"
        )
        self._touch_info_yaml(app_root_path)
        d = sgtk.descriptor.create_descriptor(
            self.tk.shotgun,
            sgtk.descriptor.Descriptor.CONFIG,
            {"type": "app_store", "name": "tk-testbundlefactory"},
            resolve_latest=True
        )
        self.assertEqual(d.get_uri(), "sgtk:descriptor:app_store?version=v0.2.3&name=tk-testbundlefactory")

        # we can do a direct lookup even when the version flag is set
        # but it will result in a latest version translation
        d = sgtk.descriptor.create_descriptor(
            self.tk.shotgun,
            sgtk.descriptor.Descriptor.CONFIG,
            {"type": "app_store", "version": "v9999.1.6", "name": "tk-testbundlefactory"},
            resolve_latest=True
        )
        self.assertEqual(d.get_uri(), "sgtk:descriptor:app_store?version=v0.2.3&name=tk-testbundlefactory")


    def test_alt_cache_root(self):
        """
        Testing descriptor constructor in alternative cache location
        """
        sg = self.tk.shotgun

        # make a unique bundleroot
        bundle_root = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)

        os.makedirs(bundle_root)

        d = sgtk.descriptor.create_descriptor(
            sg,
            sgtk.descriptor.Descriptor.CONFIG,
            {"type": "app_store", "version": "v0.4.3", "name": "tk-testaltcacheroot2"},
            bundle_root
        )

        # get_path() returns none if path doesn't exists
        self.assertEqual(d.get_path(), None)

        # now create info.yml file and try again
        app_root_path = os.path.join(
            bundle_root,
            "app_store",
            "tk-testaltcacheroot2",
            "v0.4.3")
        self._touch_info_yaml(app_root_path)
        self.assertEqual(d.get_path(), app_root_path)


    def _test_uri(self, uri, location_dict):

        computed_dict = sgtk.descriptor.descriptor_uri_to_dict(uri)
        computed_uri = sgtk.descriptor.descriptor_dict_to_uri(location_dict)
        self.assertEqual(uri, computed_uri)
        self.assertEqual(location_dict, computed_dict)

    def test_descriptor_uris(self):
        """
        Test dict/uri syntax and conversion
        """
        uri = "sgtk:descriptor:app_store?version=v0.1.2&name=tk-bundle"
        dict = {"type": "app_store", "version": "v0.1.2", "name": "tk-bundle"}
        self._test_uri(uri, dict)

        uri = "sgtk:descriptor:path?path=/foo/bar"
        dict = {"type": "path", "path": "/foo/bar"}
        self._test_uri(uri, dict)

        uri = "sgtk:descriptor:app_store?version=v0.1.2&name=tk-bundle"
        dict = {"type": "app_store", "version": "v0.1.2", "name": "tk-bundle"}
        self._test_uri(uri, dict)

        uri = "sgtk:descriptor:git?path=https%3A//github.com/shotgunsoftware/tk-core.git&version=v0.1.2"
        dict = {"type": "git", "version": "v0.1.2", "path": "https://github.com/shotgunsoftware/tk-core.git"}
        self._test_uri(uri, dict)

        uri = "sgtk:descriptor:git?path=git%40github.com%3Ashotgunsoftware/tk-core.git&version=v0.1.2"
        dict = {"type": "git", "version": "v0.1.2", "path": "git@github.com:shotgunsoftware/tk-core.git"}
        self._test_uri(uri, dict)



