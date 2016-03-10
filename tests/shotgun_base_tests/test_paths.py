# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys
import copy

from tank_vendor import yaml
from tank_test.tank_test_base import *

from tank_vendor import shotgun_base
import tank_vendor


class TestBasePaths(TankTestBase):

    def setUp(self):
        super(TestBasePaths, self).setUp()

    def test_get_cache_root(self):
        """
        Tests get_cache_root
        """
        gcr = shotgun_base.get_cache_root
        if sys.platform == "win32":
            self.assertEqual(gcr(), os.path.join(os.environ["APPDATA"], "Shotgun"))
        if sys.platform == "darwin":
            self.assertEqual(gcr(), os.path.expanduser("~/Library/Caches/Shotgun"))
        if sys.platform == "linux2":
            self.assertEqual(gcr(), os.path.expanduser("~/.shotgun"))

    def test_get_site_cache_root(self):
        """
        Tests site cache root
        """

        cache_root = self.cache_root

        path = shotgun_base.get_site_cache_root("http://sg-internal")

        self.assertEqual(os.path.dirname(path), cache_root)
        self.assertEqual(os.path.basename(path), "sg-internal")

        path = shotgun_base.get_site_cache_root("http://foo.int")
        self.assertEqual(os.path.dirname(path), cache_root)
        self.assertEqual(os.path.basename(path), "foo.int")

        path = shotgun_base.get_site_cache_root("https://my-site.shotgunstudio.com")
        self.assertEqual(os.path.dirname(path), cache_root)
        self.assertEqual(os.path.basename(path), "my-site")


