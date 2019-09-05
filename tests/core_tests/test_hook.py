# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

from tank_test.tank_test_base import TankTestBase, setUpModule # noqa

import sys
import sgtk

class TestHookProperties(TankTestBase):
    """
    Test basic hook parent accessors
    """
    def setUp(self):
        super(TestHookProperties, self).setUp()
        self.setup_fixtures()

    def test_core_hook_properties(self):
        """
        Tests the parent, sgtk and tank properties
        """
        tk= sgtk.Sgtk(self.project_root)
        hook = sgtk.Hook(parent=tk)
        self.assertEqual(hook.parent, tk)
        self.assertEqual(hook.sgtk, tk)
        self.assertEqual(hook.tank, tk)

    def test_no_parent_hook_properties(self):
        """
        Tests when no parent is defined
        """
        hook = sgtk.Hook(parent=None)
        self.assertEqual(hook.parent, None)
        self.assertEqual(hook.sgtk, None)
        self.assertEqual(hook.tank, None)


class TestHookGetPublishPath(TankTestBase):
    """
    Tests the hook.get_publish_path() method
    """
    
    def test_get_publish_path_url(self):
        """
        Tests the hook.get_publish_path method for file urls
        """
        hook = sgtk.Hook(parent=self.tk)

        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "url": "file:///foo%20/bar.baz",
                "type": "Attachment",
                "name": "bar.baz",
                "link_type": "web",
                "content_type": None
            }
        }

        if sys.platform == "win32":
            expected_path = r"\foo \bar.baz"
        else:
            expected_path = "/foo /bar.baz"

        self.assertEqual(hook.get_publish_path(sg_dict), expected_path)

        self.assertEqual(
            hook.get_publish_paths([sg_dict, sg_dict]),
            [expected_path, expected_path]
        )

    def test_get_publish_path_raises(self):
        """
        Tests the hook.get_publish_path method for unsupported data
        """
        hook = sgtk.Hook(parent=self.tk)

        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": None,
        }

        self.assertRaises(
            sgtk.util.PublishPathNotDefinedError,
            hook.get_publish_path,
            sg_dict
        )
        self.assertRaises(
            sgtk.util.PublishPathNotDefinedError,
            hook.get_publish_paths,
            [sg_dict, sg_dict]
        )

        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "url": "https://www.foo.bar",
                "link_type": "web",
                "name": "bar.baz",
            }
        }

        self.assertRaises(sgtk.util.PublishPathNotSupported, hook.get_publish_path, sg_dict)
        self.assertRaises(sgtk.util.PublishPathNotSupported, hook.get_publish_paths, [sg_dict, sg_dict])

        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                "other_field": "stuff",
                "link_type": "upload",
            }
        }

        self.assertRaises(sgtk.util.PublishPathNotSupported, hook.get_publish_path, sg_dict)
        self.assertRaises(sgtk.util.PublishPathNotSupported, hook.get_publish_paths, [sg_dict, sg_dict])

    def test_get_publish_path_local_file_link(self):
        """
        Tests the hook.get_publish_path method
        """
        hook = sgtk.Hook(parent=self.tk)

        sg_dict = {
            "id": 123,
            "type": "PublishedFile",
            "code": "foo",
            "path": {
                'content_type': 'image/png',
                'id': 25826,
                'link_type': 'local',
                'local_path': None,
                'local_path_linux': '/local/path/to/file.ext',
                'local_path_mac': '/local/path/to/file.ext',
                'local_path_windows': r'c:\local\path\to\file.ext',
                'local_storage': {'id': 39,
                               'name': 'home',
                               'type': 'LocalStorage'},
                'name': 'foo.png',
                'type': 'Attachment',
                'url': 'file:///local/path/to/file.ext'
            }
        }

        # get the current os platform
        local_path = {
            "win32": sg_dict["path"]["local_path_windows"],
            "linux2": sg_dict["path"]["local_path_linux"],
            "darwin": sg_dict["path"]["local_path_mac"],
        }[sys.platform]
        sg_dict["path"]["local_path"] = local_path

        if sys.platform == "win32":
            expected_path = r'c:\local\path\to\file.ext'
        else:
            expected_path = "/local/path/to/file.ext"

        self.assertEqual(hook.get_publish_path(sg_dict), expected_path)

        self.assertEqual(
            hook.get_publish_paths([sg_dict, sg_dict]),
            [expected_path, expected_path]
        )
