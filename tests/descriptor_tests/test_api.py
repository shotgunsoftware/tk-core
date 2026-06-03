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
import tank

from tank_test.tank_test_base import ShotgunTestBase
from tank_test.tank_test_base import setUpModule  # noqa


class TestApi(ShotgunTestBase):
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
        pass
    def test_latest(self):
        pass
    def test_alt_cache_root(self):
        pass
    def _test_uri_to_dict(self, uri, location_dict):
        """
        Tests conversion from dict to uri
        :param uri: descriptor uri
        :param location_dict: expected descriptor dict
        """
        computed_dict = sgtk.descriptor.descriptor_uri_to_dict(uri)
        self.assertEqual(location_dict, computed_dict)

    def _test_dict_to_uri(self, uri, location_dict):
        """
        Tests conversion from uri to dict
        :param uri: descriptor uri
        :param location_dict: expected descriptor dict
        """
        computed_uri = sgtk.descriptor.descriptor_dict_to_uri(location_dict)
        self.assertEqual(uri, computed_uri)

    def test_descriptor_uris(self):
        pass
    def test_backwards_compatible(self):
        pass
