# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import with_statement

import sys

from tank_test.tank_test_base import setUpModule # noqa
from tank_test.tank_test_base import TankTestBase

from tank.util import ShotgunPath


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
            ShotgunPath.SHOTGUN_PATH_FIELDS,
            ["windows_path", "linux_path", "mac_path"]
        )

        sg = ShotgunPath.from_shotgun_dict(
            {"windows_path": "C:\\temp", "mac_path": "/tmp", "linux_path": "/tmp2", "foo": "bar"}
        )

        self.assertEqual(sg.windows, "C:\\temp")
        self.assertEqual(sg.macosx, "/tmp")
        self.assertEqual(sg.linux, "/tmp2")

        sg = ShotgunPath.from_shotgun_dict(
            {"windows_path": "C:\\temp", "mac_path": None, "foo": "bar"}
        )

        self.assertEqual(sg.windows, "C:\\temp")
        self.assertEqual(sg.macosx, None)
        self.assertEqual(sg.linux, None)

        sys_paths = ShotgunPath.from_system_dict(
            {"win32": "C:\\temp", "darwin": "/tmp", "linux2": "/tmp2", "foo": "bar"}
        )

        self.assertEqual(sys_paths.windows, "C:\\temp")
        self.assertEqual(sys_paths.macosx, "/tmp")
        self.assertEqual(sys_paths.linux, "/tmp2")

        sys_paths = ShotgunPath.from_system_dict(
            {"win32": "C:\\temp", "darwin": None, "foo": "bar"}
        )

        self.assertEqual(sys_paths.windows, "C:\\temp")
        self.assertEqual(sys_paths.macosx, None)
        self.assertEqual(sys_paths.linux, None)

        if sys.platform == "win32":
            curr = ShotgunPath.from_current_os_path("\\\\server\\mount\\path")
            self.assertEqual(curr.windows, "\\\\server\\mount\\path")
            self.assertEqual(curr.macosx, None)
            self.assertEqual(curr.linux, None)
            self.assertEqual(curr.current_os, curr.windows)

        if sys.platform == "linux2":
            curr = ShotgunPath.from_current_os_path("/tmp/foo/bar")
            self.assertEqual(curr.windows, None)
            self.assertEqual(curr.macosx, None)
            self.assertEqual(curr.linux, "/tmp/foo/bar")
            self.assertEqual(curr.current_os, curr.linux)

        if sys.platform == "darwin":
            curr = ShotgunPath.from_current_os_path("/tmp/foo/bar")
            self.assertEqual(curr.windows, None)
            self.assertEqual(curr.macosx, "/tmp/foo/bar")
            self.assertEqual(curr.linux, None)
            self.assertEqual(curr.current_os, curr.macosx)

        std_constructor = ShotgunPath("C:\\temp", "/tmp", "/tmp2")
        self.assertEqual(std_constructor.windows, "C:\\temp")
        self.assertEqual(std_constructor.macosx, "/tmp2")
        self.assertEqual(std_constructor.linux, "/tmp")

    def test_property_access(self):
        """
        Test getters and setters
        """
        # check that setters sanitize the input
        std_constructor = ShotgunPath()
        std_constructor.windows = "C:\\temp\\"
        std_constructor.macosx = "/tmp/"
        std_constructor.linux = "/tmp2/"
        self.assertEqual(std_constructor.windows, "C:\\temp")
        self.assertEqual(std_constructor.macosx, "/tmp")
        self.assertEqual(std_constructor.linux, "/tmp2")

    def test_sanitize(self):
        """
        Tests site cache root
        """
        std_constructor = ShotgunPath("C:\\temp\\", "/tmp/", "/tmp2/")
        self.assertEqual(std_constructor.windows, "C:\\temp")
        self.assertEqual(std_constructor.macosx, "/tmp2")
        self.assertEqual(std_constructor.linux, "/tmp")

        std_constructor = ShotgunPath("C:/temp/", "///tmp//", "//tmp2/")
        self.assertEqual(std_constructor.windows, "C:\\temp")
        self.assertEqual(std_constructor.macosx, "/tmp2")
        self.assertEqual(std_constructor.linux, "/tmp")

        std_constructor = ShotgunPath("C:\\", "///tmp//", "//tmp2/")
        self.assertEqual(std_constructor.windows, "C:\\")
        self.assertEqual(std_constructor.macosx, "/tmp2")
        self.assertEqual(std_constructor.linux, "/tmp")

        # test raw sanitize logic
        sp = std_constructor._sanitize_path
        self.assertEqual(sp("/foo/bar/baz", "/"), "/foo/bar/baz")
        self.assertEqual(sp("/foo/bar/baz/", "/"), "/foo/bar/baz")
        self.assertEqual(sp("//foo//bar//baz", "/"), "/foo/bar/baz")
        self.assertEqual(sp("/foo/bar//baz", "/"), "/foo/bar/baz")
        self.assertEqual(sp("/foo\\bar//baz/////", "/"), "/foo/bar/baz")

        self.assertEqual(sp("/foo/bar/baz", "\\"), "\\foo\\bar\\baz")
        self.assertEqual(sp("c:/foo/bar/baz", "\\"), "c:\\foo\\bar\\baz")
        self.assertEqual(sp("c:/foo///bar\\\\baz//", "\\"), "c:\\foo\\bar\\baz")
        self.assertEqual(sp("/foo///bar\\\\baz//", "\\"), "\\foo\\bar\\baz")

        self.assertEqual(sp("\\\\server\\share\\foo\\bar", "\\"), "\\\\server\\share\\foo\\bar")
        self.assertEqual(sp("\\\\server\\share\\foo\\bar\\", "\\"), "\\\\server\\share\\foo\\bar")
        self.assertEqual(sp("//server/share/foo//bar", "\\"), "\\\\server\\share\\foo\\bar")

        self.assertEqual(sp("z:/", "\\"), "z:\\")
        self.assertEqual(sp("z:\\", "\\"), "z:\\")

        self.assertEqual(sp(None, "/"), None)

    def test_equality(self):
        """
        Tests site cache root
        """
        p1 = ShotgunPath("C:\\temp", "/tmp", "/tmp2")
        p2 = p1
        p3 = ShotgunPath("C:\\temp", "/tmp", "/tmp2")

        self.assertEqual(p1, p2)
        self.assertEqual(p1, p3)
        self.assertEqual(p3, p2)

        p4 = ShotgunPath("C:\\temp", "/tmp")
        self.assertNotEqual(p1, p4)

    def test_shotgun(self):
        """
        Tests site cache root
        """
        p1 = ShotgunPath("C:\\temp", "/tmp")
        self.assertEqual(p1.as_shotgun_dict(), {"windows_path": "C:\\temp", "linux_path": "/tmp", "mac_path": None})
        self.assertEqual(p1.as_shotgun_dict(include_empty=False), {"windows_path": "C:\\temp", "linux_path": "/tmp"})

    def test_join(self):
        """
        Tests site cache root
        """
        p1 = ShotgunPath("C:\\temp", "/linux", "/mac")
        p2 = p1.join("foo")
        p3 = p2.join("bar")

        self.assertEqual(p1.windows, "C:\\temp")
        self.assertEqual(p1.macosx, "/mac")
        self.assertEqual(p1.linux, "/linux")

        self.assertEqual(p2.windows, "C:\\temp\\foo")
        self.assertEqual(p2.macosx, "/mac/foo")
        self.assertEqual(p2.linux, "/linux/foo")

        self.assertEqual(p3.windows, "C:\\temp\\foo\\bar")
        self.assertEqual(p3.macosx, "/mac/foo/bar")
        self.assertEqual(p3.linux, "/linux/foo/bar")

    def test_get_shotgun_storage_key(self):
        """
        Tests get_shotgun_storage_key
        """
        gssk = ShotgunPath.get_shotgun_storage_key
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

    def test_truthiness(self):
        """
        Tests that a ShotgunPath that has no path set evaluates to False.
        """

        self.assertFalse(bool(ShotgunPath()))
        self.assertTrue(bool(ShotgunPath(windows_path="abc")))
        self.assertTrue(bool(ShotgunPath(linux_path="abc")))
        self.assertTrue(bool(ShotgunPath(macosx_path="abc")))

    def test_normalize(self):
        """
        Tests get_shotgun_storage_key
        """
        if sys.platform == "win32":
            self.assertEqual(ShotgunPath.normalize("C:/foo\\bar\\"), r"C:\foo\bar")
        else:
            self.assertEqual(ShotgunPath.normalize("/foo\\bar/"), "/foo/bar")

    def test_current_platform_file(self):
        """
        Ensures the get_file_name_from_template subtitutes the OS name correctly.
        """
        self.assertEqual(
            ShotgunPath.get_file_name_from_template(r"C:\%s.yml", "win32"),
            r"C:\Windows.yml"
        )

        self.assertEqual(
            ShotgunPath.get_file_name_from_template("/%s.yml", "linux2"),
            "/Linux.yml"
        )

        self.assertEqual(
            ShotgunPath.get_file_name_from_template("/%s.yml", "linux3"),
            "/Linux.yml"
        )

        self.assertEqual(
            ShotgunPath.get_file_name_from_template("/%s.yml", "darwin"),
            "/Darwin.yml"
        )

        with self.assertRaisesRegexp(
            ValueError,
            "Cannot resolve file name - unsupported os platform 'potato'"
        ):
            ShotgunPath.get_file_name_from_template("/%s.yml", "potato")
