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


class TestBaseUtils(TankTestBase):

    def setUp(self):
        super(TestBaseUtils, self).setUp()

    def test_get_shotgun_storage_key(self):
        """
        Tests get_shotgun_storage_key
        """
        gssk = shotgun_base.get_shotgun_storage_key
        self.assertEqual(gssk("win32"), "windows_path")
        self.assertEqual(gssk("linux2"), "linux_path")
        self.assertEqual(gssk("linux"), "linux_path")
        self.assertEqual(gssk("linux3"), "linux_path")
        self.assertEqual(gssk("darwin"), "mac_path")
        if sys.platform == "win32":
            self.assertEqual(gssk(), "windows_path")
        if sys.platform == "darwin":
            self.assertEqual(gssk(), "mac_path")
        if sys.platform == "linux2":
            self.assertEqual(gssk(), "linux_path")



    def test_path_sanitation_logic(self):
        """
        Tests that the pre-load cleanup logic for roots.yml is sound
        """

        sp = shotgun_base.sanitize_path

        self.assertEqual( sp("/foo/bar/baz", "/"), "/foo/bar/baz")
        self.assertEqual( sp("/foo/bar/baz/", "/"), "/foo/bar/baz")
        self.assertEqual( sp("//foo//bar//baz", "/"), "/foo/bar/baz")
        self.assertEqual( sp("/foo/bar//baz", "/"), "/foo/bar/baz")
        self.assertEqual( sp("/foo\\bar//baz/////", "/"), "/foo/bar/baz")


        self.assertEqual( sp("/foo/bar/baz", "\\"), "\\foo\\bar\\baz")
        self.assertEqual( sp("c:/foo/bar/baz", "\\"), "c:\\foo\\bar\\baz")
        self.assertEqual( sp("c:/foo///bar\\\\baz//", "\\"), "c:\\foo\\bar\\baz")
        self.assertEqual( sp("/foo///bar\\\\baz//", "\\"), "\\foo\\bar\\baz")

        self.assertEqual( sp("\\\\server\\share\\foo\\bar", "\\"), "\\\\server\\share\\foo\\bar")
        self.assertEqual( sp("\\\\server\\share\\foo\\bar\\", "\\"), "\\\\server\\share\\foo\\bar")
        self.assertEqual( sp("//server/share/foo//bar", "\\"), "\\\\server\\share\\foo\\bar")

        self.assertEqual( sp("z:/", "\\"), "z:\\")
        self.assertEqual( sp("z:\\", "\\"), "z:\\")

        self.assertEqual( sp(None, "/"), None)
