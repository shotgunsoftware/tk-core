# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

from tank_test.tank_test_base import *

import sgtk

class TestHookGetPublishPath(TankTestBase):
    
    def test_get_publish_path_url(self):
        """
        Tests the hook.get_publish_path method
        """
        hook = sgtk.Hook(parent=None)

        sg_dict = {
            "code": "foo",
            "path": {"url": "file:///foo%20/bar.baz"}
        }

        self.assertEqual(hook.get_publish_path(sg_dict), "/foo /bar.baz")

        self.assertEqual(
            hook.get_publish_paths([sg_dict, sg_dict]),
            ["/foo /bar.baz", "/foo /bar.baz"]
        )


    def test_get_publish_path_raises(self):
        """
        Tests the hook.get_publish_path method
        """
        hook = sgtk.Hook(parent=None)

        sg_dict = {
            "code": "foo",
        }

        self.assertRaises(sgtk.TankError, hook.get_publish_path, sg_dict)
        self.assertRaises(sgtk.TankError, hook.get_publish_paths, [sg_dict, sg_dict])

        sg_dict = {
            "code": "foo",
            "path": {"url": "https://www.foo.bar"}
        }

        self.assertRaises(sgtk.TankError, hook.get_publish_path, sg_dict)
        self.assertRaises(sgtk.TankError, hook.get_publish_paths, [sg_dict, sg_dict])

        sg_dict = {
            "code": "foo",
            "path": {"other_field": "stuff"}
        }

        self.assertRaises(sgtk.TankError, hook.get_publish_path, sg_dict)
        self.assertRaises(sgtk.TankError, hook.get_publish_paths, [sg_dict, sg_dict])

    def test_get_publish_path_local_file_link(self):
        """
        Tests the hook.get_publish_path method
        """
        hook = sgtk.Hook(parent=None)

        sg_dict = {
            "code": "foo",
            "path": {"local_path": "/local/path/to/file.ext"}
        }

        self.assertEqual(
            hook.get_publish_path(sg_dict),
            "/local/path/to/file.ext"
        )

        self.assertEqual(
            hook.get_publish_paths([sg_dict, sg_dict]),
            ["/local/path/to/file.ext", "/local/path/to/file.ext"]
        )