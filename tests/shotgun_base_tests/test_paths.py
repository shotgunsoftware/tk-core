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




class TestShotgunPath(TankTestBase):
    """
    tests the ShotgunPath class
    """

    def setUp(self):
        super(TestShotgunPath, self).setUp()

    def test_construction(self):
        """
        Tests get_cache_root
        """
        self.assertEqual(
            shotgun_base.ShotgunPath.SHOTGUN_PATH_FIELDS,
            ["windows_path", "linux_path", "mac_path"]
        )

        sg = shotgun_base.ShotgunPath.from_shotgun_dict(
            {"windows_path": "C:\\temp", "mac_path": "/tmp", "linux_path": "/tmp2", "foo": "bar"}
        )

        self.assertEqual(sg.windows, "C:\\temp")
        self.assertEqual(sg.mac, "/tmp")
        self.assertEqual(sg.linux, "/tmp2")

        sg = shotgun_base.ShotgunPath.from_shotgun_dict(
            {"windows_path": "C:\\temp", "mac_path": None, "foo": "bar"}
        )

        self.assertEqual(sg.windows, "C:\\temp")
        self.assertEqual(sg.mac, None)
        self.assertEqual(sg.linux, None)

        sys_paths = shotgun_base.ShotgunPath.from_system_dict(
            {"win32": "C:\\temp", "darwin": "/tmp", "linux2": "/tmp2", "foo": "bar"}
        )

        self.assertEqual(sys_paths.windows, "C:\\temp")
        self.assertEqual(sys_paths.mac, "/tmp")
        self.assertEqual(sys_paths.linux, "/tmp2")

        sys_paths = shotgun_base.ShotgunPath.from_system_dict(
            {"win32": "C:\\temp", "darwin": None, "foo": "bar"}
        )

        self.assertEqual(sys_paths.windows, "C:\\temp")
        self.assertEqual(sys_paths.mac, None)
        self.assertEqual(sys_paths.linux, None)

        if sys.platform == "win32":
            curr = shotgun_base.ShotgunPath.from_current_os_path("\\\\server\\mount\\path")
            self.assertEqual(curr.windows, "\\\\server\\mount\\path")
            self.assertEqual(curr.mac, None)
            self.assertEqual(curr.linux, None)
            self.assertEqual(curr.current_os, curr.windows)

        if sys.platform == "linux2":
            curr = shotgun_base.ShotgunPath.from_current_os_path("/tmp/foo/bar")
            self.assertEqual(curr.windows, None)
            self.assertEqual(curr.mac, None)
            self.assertEqual(curr.linux, "/tmp/foo/bar")
            self.assertEqual(curr.current_os, curr.linux)

        if sys.platform == "darwin":
            curr = shotgun_base.ShotgunPath.from_current_os_path("/tmp/foo/bar")
            self.assertEqual(curr.windows, None)
            self.assertEqual(curr.mac, "/tmp/foo/bar")
            self.assertEqual(curr.linux, None)
            self.assertEqual(curr.current_os, curr.mac)

        std_constructor = shotgun_base.ShotgunPath("C:\\temp", "/tmp", "/tmp2")
        self.assertEqual(std_constructor.windows, "C:\\temp")
        self.assertEqual(std_constructor.mac, "/tmp2")
        self.assertEqual(std_constructor.linux, "/tmp")


    def test_sanitize(self):
        """
        Tests site cache root
        """
        std_constructor = shotgun_base.ShotgunPath("C:\\temp\\", "/tmp/", "/tmp2/")
        self.assertEqual(std_constructor.windows, "C:\\temp")
        self.assertEqual(std_constructor.mac, "/tmp2")
        self.assertEqual(std_constructor.linux, "/tmp")

        std_constructor = shotgun_base.ShotgunPath("C:/temp/", "///tmp//", "//tmp2/")
        self.assertEqual(std_constructor.windows, "C:\\temp")
        self.assertEqual(std_constructor.mac, "/tmp2")
        self.assertEqual(std_constructor.linux, "/tmp")

        std_constructor = shotgun_base.ShotgunPath("C:\\", "///tmp//", "//tmp2/")
        self.assertEqual(std_constructor.windows, "C:\\")
        self.assertEqual(std_constructor.mac, "/tmp2")
        self.assertEqual(std_constructor.linux, "/tmp")

    def test_equality(self):
        """
        Tests site cache root
        """
        p1 = shotgun_base.ShotgunPath("C:\\temp", "/tmp", "/tmp2")
        p2 = p1
        p3 = shotgun_base.ShotgunPath("C:\\temp", "/tmp", "/tmp2")

        self.assertEqual(p1, p2)
        self.assertEqual(p1, p3)
        self.assertEqual(p3, p2)

        p4 = shotgun_base.ShotgunPath("C:\\temp", "/tmp")
        self.assertNotEqual(p1, p4)

    def test_shotgun(self):
        """
        Tests site cache root
        """
        p1 = shotgun_base.ShotgunPath("C:\\temp", "/tmp")
        self.assertEqual(p1.as_shotgun_dict(), {"windows_path": "C:\\temp", "linux_path": "/tmp", "mac_path": None})
        self.assertEqual(p1.as_shotgun_dict(include_empty=False), {"windows_path": "C:\\temp", "linux_path": "/tmp"})

    def test_join(self):
        """
        Tests site cache root
        """
        p1 = shotgun_base.ShotgunPath("C:\\temp", "/linux", "/mac")
        p2 = p1.join("foo")
        p3 = p2.join("bar")

        self.assertEqual(p1.windows, "C:\\temp")
        self.assertEqual(p1.mac, "/mac")
        self.assertEqual(p1.linux, "/linux")

        self.assertEqual(p2.windows, "C:\\temp\\foo")
        self.assertEqual(p2.mac, "/mac/foo")
        self.assertEqual(p2.linux, "/linux/foo")

        self.assertEqual(p3.windows, "C:\\temp\\foo\\bar")
        self.assertEqual(p3.mac, "/mac/foo/bar")
        self.assertEqual(p3.linux, "/linux/foo/bar")
