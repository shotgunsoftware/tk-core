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
from tank_vendor import shotgun_deploy
from tank_vendor import shotgun_base



class TestApi(TankTestBase):
    """
    Testing the Shotgun deploy main API methods
    """

    def test_factory(self):
        """
        Basic test of descriptor construction
        """
        sg = self.tk.shotgun
        d = shotgun_deploy.create_descriptor(
                sg,
                shotgun_deploy.Descriptor.CONFIG,
                {"type": "app_store", "version": "v0.1.2", "name": "tk-bundle"}
        )

        self.assertEqual(
                d.get_path(),
                os.path.join(
                        shotgun_base.get_cache_root(), "bundle_cache", "app_store", "tk-bundle", "v0.1.2"
                )
        )


    def test_alt_cache_root(self):
        """
        Testing descriptor constructor in alternative cache location
        """
        sg = self.tk.shotgun

        bundle_root = tempfile.gettempdir()

        d = shotgun_deploy.create_descriptor(
                sg,
                shotgun_deploy.Descriptor.CONFIG,
                {"type": "app_store", "version": "v0.1.2", "name": "tk-bundle"},
                bundle_root
        )

        # get_path() returns none if path doesn't exists
        self.assertEqual(d.get_path(), None)

        app_root_path = os.path.join(bundle_root, "app_store", "tk-bundle", "v0.1.2")
        shotgun_base.ensure_folder_exists(app_root_path)
        fh = open(os.path.join(app_root_path, "info.yml"), "wt")
        fh.write("fo")
        fh.close()

        self.assertEqual(d.get_path(), app_root_path)


    def _test_uri(self, uri, dict):
        computed_dict = shotgun_deploy.io_descriptor.location_uri_to_dict(uri)
        computed_uri = shotgun_deploy.io_descriptor.location_dict_to_uri(dict)
        self.assertEqual(uri, computed_uri)
        self.assertEqual(dict, computed_dict)

    def test_descriptor_uris(self):

        uri = "sgtk:location:app_store?version=v0.1.2&name=tk-bundle"
        dict = {"type": "app_store", "version": "v0.1.2", "name": "tk-bundle"}
        self._test_uri(uri, dict)

        uri = "sgtk:location:path?path=/foo/bar"
        dict = {"type": "path", "path": "/foo/bar"}
        self._test_uri(uri, dict)
