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
import os
import sys

from mock import patch, call

import sgtk
from tank import context, errors
from tank.util import is_linux, is_macos, is_windows
from tank_test.tank_test_base import TankTestBase, setUpModule
from tank_vendor import six
from tank_vendor.shotgun_api3.lib import sgsix


class TestCoreHook(TankTestBase):
    """
    Tests the resolve_publish core hook
    """

    def setUp(self):
        super(TestCoreHook, self).setUp()
        self.setup_fixtures(name="publish_resolve")

    def test_unsupported_url(self):
        """
        Tests url that the core hook does not support
        """
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "url": "unsupported://www.url.com",
                "type": "Attachment",
                "name": "url.com",
                "link_type": "web",
                "content_type": None,
            },
        }

        self.assertRaises(
            sgtk.util.PublishPathNotSupported,
            sgtk.util.resolve_publish_path,
            self.tk,
            sg_dict,
        )

    def test_supported_url(self):
        """
        Tests url that the core hook handles
        """
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "url": "supported://www.url.com",
                "type": "Attachment",
                "name": "url.com",
                "link_type": "web",
                "content_type": None,
            },
        }

        local_path = sgtk.util.resolve_publish_path(self.tk, sg_dict)
        self.assertEqual(local_path, "/supported/from/core/hook")

    def test_supported_override(self):
        """
        Tests url that the core hook can override existing behavior
        """
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "url": "file://www.url.com",
                "type": "Attachment",
                "name": "url.com",
                "link_type": "web",
                "content_type": None,
            },
        }

        local_path = sgtk.util.resolve_publish_path(self.tk, sg_dict)
        self.assertEqual(local_path, "/file/from/core/hook")


class TestUnsupported(TankTestBase):
    """
    Tests unsupported publish scenarios
    """

    def setUp(self):
        super(TestUnsupported, self).setUp()
        self.setup_fixtures()

    def test_no_path(self):
        """
        Test publishes with no path set
        """
        sg_dict = {"id": 123, "type": "PublishedFile", "code": "foo", "path": None}

        self.assertRaises(
            sgtk.util.PublishPathNotDefinedError,
            sgtk.util.resolve_publish_path,
            self.tk,
            sg_dict,
        )

    def test_upload(self):
        """
        Test publishes with uploaded data
        """
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "content_type": "image/jpeg",
                "link_type": "upload",
                "name": "western1FULL.jpg",
                "url": "https://superdeathcarracer.shotgunstudio.com/file_serve/attachment/538",
            },
        }

        self.assertRaises(
            sgtk.util.PublishPathNotSupported,
            sgtk.util.resolve_publish_path,
            self.tk,
            sg_dict,
        )

    def test_unsupported_url(self):
        """
        test non-file urls
        """
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "url": "https://www.url.com",
                "type": "Attachment",
                "name": "url.com",
                "link_type": "web",
                "content_type": None,
            },
        }

        self.assertRaises(
            sgtk.util.PublishPathNotSupported,
            sgtk.util.resolve_publish_path,
            self.tk,
            sg_dict,
        )


class TestLocalFileLink(TankTestBase):
    """
    Tests path resolution of publishes to local file links
    """

    def setUp(self):
        super(TestLocalFileLink, self).setUp()
        self.setup_fixtures()

        self.storage = {
            "type": "LocalStorage",
            "id": 2,
            "code": "home",
            "mac_path": "/local",
            "windows_path": "x:\\",
            "linux_path": "/local",
        }

        self.add_to_sg_mock_db([self.storage])

    def tearDown(self):

        if "SHOTGUN_PATH_WINDOWS_HOME" in os.environ:
            del os.environ["SHOTGUN_PATH_WINDOWS_HOME"]

        if "SHOTGUN_PATH_MAC_HOME" in os.environ:
            del os.environ["SHOTGUN_PATH_MAC_HOME"]

        if "SHOTGUN_PATH_LINUX_HOME" in os.environ:
            del os.environ["SHOTGUN_PATH_LINUX_HOME"]

        super(TestLocalFileLink, self).tearDown()

    def test_basic_case(self):
        """
        Test no overrides
        """
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "content_type": "image/png",
                "id": 25826,
                "link_type": "local",
                "local_path": None,
                "local_path_linux": "/local/path/to/file.ext",
                "local_path_mac": "/local/path/to/file.ext",
                "local_path_windows": r"X:\path\to\file.ext",
                "local_storage": {"id": 2, "name": "home", "type": "LocalStorage"},
                "name": "foo.png",
                "type": "Attachment",
                "url": "file:///local/path/to/file.ext",
            },
        }

        # get the current os platform
        local_path = {
            "win32": sg_dict["path"]["local_path_windows"],
            "linux2": sg_dict["path"]["local_path_linux"],
            "darwin": sg_dict["path"]["local_path_mac"],
        }[sgsix.platform]
        sg_dict["path"]["local_path"] = local_path

        evaluated_path = sgtk.util.resolve_publish_path(self.tk, sg_dict)
        self.assertEqual(evaluated_path, local_path)

    def test_env_var_warning(self):
        """
        Tests that if the current os is defined
        in the shotgun local storage defs, and an env var
        is also defined, the local storage takes precedence.
        """
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "content_type": "image/png",
                "id": 25826,
                "link_type": "local",
                "local_path": None,
                "local_path_linux": "/local/path/to/file.ext",
                "local_path_mac": "/local/path/to/file.ext",
                "local_path_windows": r"X:\path\to\file.ext",
                "local_storage": {"id": 2, "name": "home", "type": "LocalStorage"},
                "name": "foo.png",
                "type": "Attachment",
                "url": "file:///local/path/to/file.ext",
            },
        }

        # set up env var overrides
        os.environ["SHOTGUN_PATH_WINDOWS_HOME"] = "Y:\\"
        os.environ["SHOTGUN_PATH_MAC_HOME"] = "/some_other_root"
        os.environ["SHOTGUN_PATH_LINUX_HOME"] = "/some_other_root"

        # get the current os platform
        local_path = {
            "win32": sg_dict["path"]["local_path_windows"],
            "linux2": sg_dict["path"]["local_path_linux"],
            "darwin": sg_dict["path"]["local_path_mac"],
        }[sgsix.platform]
        sg_dict["path"]["local_path"] = local_path

        evaluated_path = sgtk.util.resolve_publish_path(self.tk, sg_dict)
        self.assertEqual(evaluated_path, local_path)


class TestLocalFileLinkRaises(TankTestBase):
    """
    Tests path resolution of publishes to local file links

    Tests that if the current os is not recognized,
    PublishPathNotDefinedError is defined.
    """

    def setUp(self):
        super(TestLocalFileLinkRaises, self).setUp()
        self.setup_fixtures()

    def test_raises(self):
        """
        Tests that if the current os is not recognized,
        PublishPathNotDefinedError is defined.
        """

        # add a storage and omit current os
        self.storage = {
            "type": "LocalStorage",
            "id": 2,
            "code": "home",
            "mac_path": "/local",
            "windows_path": "x:\\",
            "linux_path": "/local",
        }

        current_path_field = {
            "win32": "windows_path",
            "linux2": "linux_path",
            "darwin": "mac_path",
        }[sgsix.platform]

        self.storage[current_path_field] = None
        self.add_to_sg_mock_db([self.storage])

        # add a publish and omit current os
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "content_type": "image/png",
                "id": 25826,
                "link_type": "local",
                "local_path": None,
                "local_path_linux": "/local/path/to/file.ext",
                "local_path_mac": "/local/path/to/file.ext",
                "local_path_windows": r"X:\path\to\file.ext",
                "local_storage": {"id": 2, "name": "home", "type": "LocalStorage"},
                "name": "foo.png",
                "type": "Attachment",
                "url": "file:///local/path/to/file.ext",
            },
        }

        current_path_field = {
            "win32": "local_path_windows",
            "linux2": "local_path_linux",
            "darwin": "local_path_mac",
        }[sgsix.platform]

        sg_dict["path"][current_path_field] = None

        self.assertRaises(
            sgtk.util.PublishPathNotDefinedError,
            sgtk.util.resolve_publish_path,
            self.tk,
            sg_dict,
        )


class TestLocalFileLinkEnvVarOverride(TankTestBase):
    """
    Tests path resolution of publishes to local file links

    Tests that if the current os is not defined
    in the shotgun local storage defs, we can override
    it by setting an env var.
    """

    def setUp(self):
        super(TestLocalFileLinkEnvVarOverride, self).setUp()
        self.setup_fixtures()

    def tearDown(self):

        if "SHOTGUN_PATH_WINDOWS_HOME" in os.environ:
            del os.environ["SHOTGUN_PATH_WINDOWS_HOME"]

        if "SHOTGUN_PATH_MAC_HOME" in os.environ:
            del os.environ["SHOTGUN_PATH_MAC_HOME"]

        if "SHOTGUN_PATH_LINUX_HOME" in os.environ:
            del os.environ["SHOTGUN_PATH_LINUX_HOME"]

        super(TestLocalFileLinkEnvVarOverride, self).tearDown()

    def test_env_var(self):
        """
        Tests that if the current os is not defined
        in the shotgun local storage defs, we can override
        it by setting an env var.
        """
        # add a storage and omit current os
        self.storage = {
            "type": "LocalStorage",
            "id": 2,
            "code": "home",
            "mac_path": "/local",
            "windows_path": "x:\\",
            "linux_path": "/local",
        }

        current_path_field = {
            "win32": "windows_path",
            "linux2": "linux_path",
            "darwin": "mac_path",
        }[sgsix.platform]

        self.storage[current_path_field] = None
        self.add_to_sg_mock_db([self.storage])

        # add a publish record
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "content_type": "image/png",
                "id": 25826,
                "link_type": "local",
                "local_path": None,
                "local_path_linux": "/local/path/to/file.ext",
                "local_path_mac": "/local/path/to/file.ext",
                "local_path_windows": r"X:\path\to\file.ext",
                "local_storage": {"id": 2, "name": "home", "type": "LocalStorage"},
                "name": "foo.png",
                "type": "Attachment",
                "url": "file:///local/path/to/file.ext",
            },
        }

        if is_windows():
            os.environ["SHOTGUN_PATH_WINDOWS_HOME"] = "Y:\\"
            local_path = r"Y:\path\to\file.ext"
            sg_dict["path"]["local_path_windows"] = None
        elif is_macos():
            os.environ["SHOTGUN_PATH_MAC_HOME"] = "/local_override"
            local_path = "/local_override/path/to/file.ext"
            sg_dict["path"]["local_path_mac"] = None
        elif is_linux():
            os.environ["SHOTGUN_PATH_LINUX_HOME"] = "/local_override"
            local_path = "/local_override/path/to/file.ext"
            sg_dict["path"]["local_path_linux"] = None

        evaluated_path = sgtk.util.resolve_publish_path(self.tk, sg_dict)
        self.assertEqual(evaluated_path, local_path)


class TestUrlNoStorages(TankTestBase):
    """
    Tests urls with no storages defined
    """

    def setUp(self):
        super(TestUrlNoStorages, self).setUp()
        self.setup_fixtures()

    def test_nix_path(self):
        """
        Tests resolving a unix/macosx file://path url
        """
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "url": "file:///foo%20/bar.baz",
                "type": "Attachment",
                "name": "bar.baz",
                "link_type": "web",
                "content_type": None,
            },
        }

        local_path = sgtk.util.resolve_publish_path(self.tk, sg_dict)
        if is_windows():
            self.assertEqual(r"\foo \bar.baz", local_path)
        else:
            self.assertEqual("/foo /bar.baz", local_path)

    def test_windows_drive_path(self):
        """
        Tests resolving a windows file://path url with a drive letter
        """
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "url": "file:///C:/foo/bar/baz",
                "type": "Attachment",
                "name": "bar.baz",
                "link_type": "web",
                "content_type": None,
            },
        }

        local_path = sgtk.util.resolve_publish_path(self.tk, sg_dict)
        if is_windows():
            self.assertEqual(r"C:\foo\bar\baz", local_path)
        else:
            self.assertEqual("C:/foo/bar/baz", local_path)

    def test_windows_unc_path(self):
        """
        Tests resolving a windows unc path style file://path url
        """
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "url": "file://share/foo/bar/baz",
                "type": "Attachment",
                "name": "bar.baz",
                "link_type": "web",
                "content_type": None,
            },
        }

        local_path = sgtk.util.resolve_publish_path(self.tk, sg_dict)
        if is_windows():
            self.assertEqual(r"\\share\foo\bar\baz", local_path)
        else:
            self.assertEqual("//share/foo/bar/baz", local_path)


class TestUrlWithEnvVars(TankTestBase):
    """
    Tests url resolution with local storages and environment variables
    """

    def setUp(self):
        super(TestUrlWithEnvVars, self).setUp()
        self.setup_fixtures()

        # set override
        os.environ["SHOTGUN_PATH_WINDOWS"] = r"\\share"
        os.environ["SHOTGUN_PATH_MAC"] = "/mac"
        os.environ["SHOTGUN_PATH_LINUX"] = "/linux"

        if six.PY3:
            # Because of dictionary order differences between Python2 and 3, a
            # bug in storage resolution is being hit by tests in Python 3 now
            # that hadn't previously been discovered.  A ticket has been logged
            # (SG-14149), but in the meantime we will continue to test the rest
            # of the functionality in Python 3 by altering the test data to
            # avoid hitting the bug.
            os.environ["SHOTGUN_PATH_WINDOWS_2"] = "X:\\"
            os.environ["SHOTGUN_PATH_MAC_2"] = "/altmac"
            os.environ["SHOTGUN_PATH_LINUX_2"] = "/altlinux"
        else:
            os.environ["SHOTGUN_PATH_WINDOWS_2"] = "X:\\"
            os.environ["SHOTGUN_PATH_MAC_2"] = "/mac2"
            os.environ["SHOTGUN_PATH_LINUX_2"] = "/linux2"

    def tearDown(self):

        del os.environ["SHOTGUN_PATH_WINDOWS"]
        del os.environ["SHOTGUN_PATH_MAC"]
        del os.environ["SHOTGUN_PATH_LINUX"]
        del os.environ["SHOTGUN_PATH_WINDOWS_2"]
        del os.environ["SHOTGUN_PATH_MAC_2"]
        del os.environ["SHOTGUN_PATH_LINUX_2"]

        super(TestUrlWithEnvVars, self).tearDown()

    def test_no_storages(self):
        """
        Test url path resolution when no env vars match
        """
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "url": "file:///storage_3/bar.baz",
                "type": "Attachment",
                "name": "bar.baz",
                "link_type": "web",
                "content_type": None,
            },
        }

        # final paths
        expected_path = {
            "win32": r"\storage_3\bar.baz",
            "linux2": "/storage_3/bar.baz",
            "darwin": "/storage_3/bar.baz",
        }[sgsix.platform]

        evaluated_path = sgtk.util.resolve_publish_path(self.tk, sg_dict)
        self.assertEqual(evaluated_path, expected_path)

    def test_windows_unc(self):
        """
        Test url path resolution with env vars
        """
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "url": "file://share/path/to/file",
                "type": "Attachment",
                "name": "bar.baz",
                "link_type": "web",
                "content_type": None,
            },
        }

        # final paths
        expected_path = {
            "win32": r"\\share\path\to\file",
            "linux2": "/linux/path/to/file",
            "darwin": "/mac/path/to/file",
        }[sgsix.platform]

        evaluated_path = sgtk.util.resolve_publish_path(self.tk, sg_dict)
        self.assertEqual(evaluated_path, expected_path)

    def test_windows_drive(self):
        """
        Test url path resolution with env vars
        """
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "url": "file:///x:/path/to/file",
                "type": "Attachment",
                "name": "bar.baz",
                "link_type": "web",
                "content_type": None,
            },
        }

        # final paths
        expected_path = {
            "win32": os.environ["SHOTGUN_PATH_WINDOWS_2"] + r"path\to\file",
            "linux2": os.environ["SHOTGUN_PATH_LINUX_2"] + "/path/to/file",
            "darwin": os.environ["SHOTGUN_PATH_MAC_2"] + "/path/to/file",
        }[sgsix.platform]

        evaluated_path = sgtk.util.resolve_publish_path(self.tk, sg_dict)
        self.assertEqual(evaluated_path, expected_path)

    def test_nix(self):
        """
        Test url path resolution with env vars
        """
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "url": "file://" + os.environ["SHOTGUN_PATH_LINUX_2"] + "/path/to/file",
                "type": "Attachment",
                "name": "bar.baz",
                "link_type": "web",
                "content_type": None,
            },
        }

        # final paths
        expected_path = {
            "win32": os.environ["SHOTGUN_PATH_WINDOWS_2"] + r"path\to\file",
            "linux2": os.environ["SHOTGUN_PATH_LINUX_2"] + "/path/to/file",
            "darwin": os.environ["SHOTGUN_PATH_MAC_2"] + "/path/to/file",
        }[sgsix.platform]

        evaluated_path = sgtk.util.resolve_publish_path(self.tk, sg_dict)
        self.assertEqual(evaluated_path, expected_path)


class TestUrlWithStorages(TankTestBase):
    """
    Tests url resolution with local storages
    """

    def setUp(self):
        super(TestUrlWithStorages, self).setUp()

        self.setup_fixtures()

        self.storage = {
            "type": "LocalStorage",
            "id": 1,
            "code": "storage_1",
            "mac_path": "/storage1_mac",
            "windows_path": "x:\\storage1_win\\",
            "linux_path": "/storage1_linux/",
        }

        self.storage_2 = {
            "type": "LocalStorage",
            "id": 2,
            "code": "storage_2",
            "mac_path": "/storage2_mac/",
            "windows_path": r"\\storage2_win",
            "linux_path": "/storage2_linux",
        }

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.storage, self.storage_2])

    def test_no_storages(self):
        """
        Test url path resolution when no storages match
        """
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "url": "file:///storage_3/bar.baz",
                "type": "Attachment",
                "name": "bar.baz",
                "link_type": "web",
                "content_type": None,
            },
        }

        # final paths
        expected_path = {
            "win32": r"\storage_3\bar.baz",
            "linux2": "/storage_3/bar.baz",
            "darwin": "/storage_3/bar.baz",
        }[sgsix.platform]

        evaluated_path = sgtk.util.resolve_publish_path(self.tk, sg_dict)
        self.assertEqual(evaluated_path, expected_path)

    def test_local_storage_windows_unc(self):
        """
        Test url path resolution with dynamic storage lookup
        """
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "url": "file://storage2_win/path/to/file",
                "type": "Attachment",
                "name": "bar.baz",
                "link_type": "web",
                "content_type": None,
            },
        }

        # final paths
        expected_path = {
            "win32": r"\\storage2_win\path\to\file",
            "linux2": "/storage2_linux/path/to/file",
            "darwin": "/storage2_mac/path/to/file",
        }[sgsix.platform]

        evaluated_path = sgtk.util.resolve_publish_path(self.tk, sg_dict)
        self.assertEqual(evaluated_path, expected_path)

    def test_local_storage_windows_drive(self):
        """
        Test url path resolution with dynamic storage lookup
        """
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "url": "file:///x:/storage1_win/path/to/file",
                "type": "Attachment",
                "name": "bar.baz",
                "link_type": "web",
                "content_type": None,
            },
        }

        # final paths
        expected_path = {
            "win32": r"x:\storage1_win\path\to\file",
            "linux2": "/storage1_linux/path/to/file",
            "darwin": "/storage1_mac/path/to/file",
        }[sgsix.platform]

        evaluated_path = sgtk.util.resolve_publish_path(self.tk, sg_dict)
        self.assertEqual(evaluated_path, expected_path)

    def test_local_storage_nix(self):
        """
        Test url path resolution with dynamic storage lookup
        """
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "url": "file:///storage1_linux/path/to/file",
                "type": "Attachment",
                "name": "bar.baz",
                "link_type": "web",
                "content_type": None,
            },
        }

        # final paths
        expected_path = {
            "win32": r"x:\storage1_win\path\to\file",
            "linux2": "/storage1_linux/path/to/file",
            "darwin": "/storage1_mac/path/to/file",
        }[sgsix.platform]

        evaluated_path = sgtk.util.resolve_publish_path(self.tk, sg_dict)
        self.assertEqual(evaluated_path, expected_path)


class TestUrlWithStoragesAndOverrides(TankTestBase):
    """
    Tests file:// url resolution with local storages and environment overrides
    """

    def setUp(self):
        super(TestUrlWithStoragesAndOverrides, self).setUp()

        self.setup_fixtures()

        self.storage = {
            "type": "LocalStorage",
            "id": 1,
            "code": "storage_1",
            "windows_path": r"\\storage_win",
        }

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.storage])

    def test_augument_local_storage(self):
        """
        Test that we can add add an os platform via an env var
        """
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "url": "file://storage_win/path/to/file",
                "type": "Attachment",
                "name": "bar.baz",
                "link_type": "web",
                "content_type": None,
            },
        }

        os.environ["SHOTGUN_PATH_MAC_STORAGE_1"] = "/storage_mac"
        os.environ["SHOTGUN_PATH_LINUX_STORAGE_1"] = "/storage_linux"

        # final paths
        expected_path = {
            "win32": r"\\storage_win\path\to\file",
            "linux2": "/storage_linux/path/to/file",
            "darwin": "/storage_mac/path/to/file",
        }[sgsix.platform]

        evaluated_path = sgtk.util.resolve_publish_path(self.tk, sg_dict)
        self.assertEqual(evaluated_path, expected_path)


class TestUrlWithStoragesAndOverrides2(TankTestBase):
    """
    Tests file:// url resolution with local storages and
    additive environment overrides.
    """

    def setUp(self):
        super(TestUrlWithStoragesAndOverrides2, self).setUp()

        self.setup_fixtures()

        self.storage = {
            "type": "LocalStorage",
            "id": 1,
            "code": "storage_1",
            "mac_path": "/storage_mac",
            "windows_path": "x:\\storage_win\\",
            "linux_path": "/storage_linux/",
        }

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.storage])

        os.environ["SHOTGUN_PATH_MAC_STORAGE_1"] = "/storage_mac_alt"
        os.environ["SHOTGUN_PATH_LINUX_STORAGE_1"] = "/storage_linux_alt"
        os.environ["SHOTGUN_PATH_WINDOWS_STORAGE_1"] = "x:\\storage_win_alt"

    def tearDown(self):
        del os.environ["SHOTGUN_PATH_MAC_STORAGE_1"]
        del os.environ["SHOTGUN_PATH_LINUX_STORAGE_1"]
        del os.environ["SHOTGUN_PATH_WINDOWS_STORAGE_1"]

        super(TestUrlWithStoragesAndOverrides2, self).tearDown()

    def test_augument_local_storage(self):
        """
        Tests that local storages take precedence over env vars.
        """
        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "url": "file:///x:/storage_win/path/to/file",
                "type": "Attachment",
                "name": "bar.baz",
                "link_type": "web",
                "content_type": None,
            },
        }

        # final paths
        expected_path = {
            "win32": r"x:\storage_win\path\to\file",
            "linux2": "/storage_linux/path/to/file",
            "darwin": "/storage_mac/path/to/file",
        }[sgsix.platform]

        evaluated_path = sgtk.util.resolve_publish_path(self.tk, sg_dict)
        self.assertEqual(evaluated_path, expected_path)
