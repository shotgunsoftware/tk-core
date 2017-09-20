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
import datetime
import threading
import urlparse
import unittest2 as unittest
import logging

from mock import patch, call

import tank
from tank import context, errors
from tank_test.tank_test_base import TankTestBase, setUpModule
from tank.template import TemplatePath
from tank.templatekey import SequenceKey
from tank.authentication.user import ShotgunUser
from tank.authentication.user_impl import SessionUser
from tank.descriptor import Descriptor
from tank.descriptor.io_descriptor.appstore import IODescriptorAppStore


class TestShotgunRegisterPublish(TankTestBase):
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestShotgunRegisterPublish, self).setUp()

        self.setup_fixtures()

        self.storage = {
            "type": "LocalStorage",
            "id": 1,
            "code": "Tank"
        }

        self.storage_2 = {
            "type": "LocalStorage",
            "id": 2,
            "code": "my_other_storage",
            "mac_path": "/tmp/nix",
            "windows_path": r"x:\tmp\win",
            "linux_path": "/tmp/nix"
        }

        self.storage_3 = {
            "type": "LocalStorage",
            "id": 3,
            "code": "unc paths",
            "windows_path": r"\\server\share",
        }

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.storage, self.storage_2, self.storage_3])

        self.shot = {"type": "Shot",
                    "name": "shot_name",
                    "id": 2,
                    "project": self.project}
        self.step = {"type": "Step", "name": "step_name", "id": 4}

        context_data = {
            "tk": self.tk,
            "project": self.project,
            "entity": self.shot,
            "step": self.step,
        }

        self.context = context.Context(**context_data)
        self.path = os.path.join(self.project_root, "foo", "bar")
        self.name = "Test Publish"
        self.version = 1

    def test_sequence_abstracted_path(self):
        """Test that if path supplied represents a sequence, the abstract version of that
        sequence is used."""

        # make sequence key
        keys = { "seq": tank.templatekey.SequenceKey("seq", format_spec="03")}
        # make sequence template
        seq_template = tank.template.TemplatePath("/folder/name_{seq}.ext", keys, self.project_root)
        self.tk.templates["sequence_template"] = seq_template

        seq_path = os.path.join(self.project_root, "folder", "name_001.ext")

        create_data = []
        # wrap create so we can keep tabs of things
        def create_mock(entity_type, data, return_fields=None):
            create_data.append(data)
            return real_create(entity_type, data, return_fields)

        real_create = self.tk.shotgun.create
        self.tk.shotgun.create = create_mock

        publish_data = tank.util.register_publish(
            self.tk,
            self.context,
            seq_path,
            self.name,
            self.version,
            dry_run=True
        )
        self.assertIsInstance(publish_data, dict)

        # mock sg.create, check it for path value
        try:
            tank.util.register_publish(self.tk, self.context, seq_path, self.name, self.version)
        finally:
            self.tk.shotgun.create = real_create


        # check that path is modified before sent to shotgun
        expected_path = os.path.join(self.project_root, "folder", "name_%03d.ext")
        project_name = os.path.basename(self.project_root)
        expected_path_cache = "%s/%s/%s" % (project_name, "folder", "name_%03d.ext")


        actual_path = create_data[0]["path"]["local_path"]
        actual_path_cache = create_data[0]["path_cache"]

        self.assertEqual(expected_path, actual_path)
        self.assertEqual(expected_path_cache, actual_path_cache)

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.create")
    def test_url_paths(self, create_mock):
        """Tests the passing of urls via the path."""

        publish_data = tank.util.register_publish(
            self.tk,
            self.context,
            "file:///path/to/file with spaces.png",
            self.name,
            self.version,
            dry_run=True
        )
        self.assertIsInstance(publish_data, dict)

        tank.util.register_publish(
            self.tk,
            self.context,
            "file:///path/to/file with spaces.png",
            self.name,
            self.version)

        create_data = create_mock.call_args
        args, kwargs = create_data
        sg_dict = args[1]

        self.assertEqual(
            sg_dict["path"],
            {
                'url': 'file:///path/to/file%20with%20spaces.png',
                'name': 'file with spaces.png'
            }
        )
        self.assertEqual("pathcache" not in sg_dict, True)

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.create")
    def test_url_paths_host(self, create_mock):
        """Tests the passing of urls via the path."""

        publish_data = tank.util.register_publish(
            self.tk,
            self.context,
            "https://site.com",
            self.name,
            self.version,
            dry_run=True
        )
        self.assertIsInstance(publish_data, dict)

        tank.util.register_publish(
            self.tk,
            self.context,
            "https://site.com",
            self.name,
            self.version)

        create_data = create_mock.call_args
        args, kwargs = create_data
        sg_dict = args[1]

        self.assertEqual(
            sg_dict["path"],
            {
                'url': 'https://site.com',
                'name': 'site.com'
            }
        )
        self.assertEqual("pathcache" not in sg_dict, True)

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.create")
    def test_local_storage_publish(self, create_mock):
        """
        Tests that we generate local file links when publishing to a known storage
        """
        if sys.platform == "win32":
            values = [
                r"x:\tmp\win\path\to\file.txt",
                r"\\server\share\path\to\file.txt",
            ]

        else:
            values = ["/tmp/nix/path/to/file.txt"]

        # Various paths we support, Unix and Windows styles
        for local_path in values:

            publish_data = tank.util.register_publish(
                self.tk,
                self.context,
                local_path,
                self.name,
                self.version,
                dry_run=True
            )
            self.assertIsInstance(publish_data, dict)

            tank.util.register_publish(
                self.tk,
                self.context,
                local_path,
                self.name,
                self.version
            )

            create_data = create_mock.call_args
            args, kwargs = create_data
            sg_dict = args[1]

            self.assertEqual(
                sg_dict["path"],
                {"local_path": local_path}
            )

            self.assertTrue("pathcache" not in sg_dict)

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.create")
    def test_freeform_publish(self, create_mock):
        """
        Tests that we generate url file:// links for freeform paths
        """
        if sys.platform == "win32":
            values = {
                "C:/path/to/test file.png": {
                    "url": "file:///C:/path/to/test%20file.png",
                    "name": "test file.png"
                },
                "e:/path/to/test file.png": {
                    "url": "file:///E:/path/to/test%20file.png",
                    "name": "test file.png"
                },
                "//path/to/test file.png": {
                    "url": "file://path/to/test%20file.png",
                    "name": "test file.png"
                },
                r"C:\path\to\test file.png": {
                    "url": "file:///C:/path/to/test%20file.png",
                    "name": "test file.png"
                },
                r"e:\path\to\test file.png": {
                    "url": "file:///E:/path/to/test%20file.png",
                    "name": "test file.png"
                },
                r"\\path\to\test file.png": {
                    "url": "file://path/to/test%20file.png",
                    "name": "test file.png"
                },
            }

        else:
            values = {
                "/path/to/test file.png": {
                    "url": "file:///path/to/test%20file.png",
                    "name": "test file.png"
                },
            }

        # Various paths we support, Unix and Windows styles
        for (local_path, path_dict) in values.iteritems():

            publish_data = tank.util.register_publish(
                self.tk,
                self.context,
                local_path,
                self.name,
                self.version,
                dry_run=True
            )
            self.assertIsInstance(publish_data, dict)

            tank.util.register_publish(
                self.tk,
                self.context,
                local_path,
                self.name,
                self.version
            )

            create_data = create_mock.call_args
            args, kwargs = create_data
            sg_dict = args[1]

            self.assertEqual(sg_dict["path"], path_dict)
            self.assertTrue("pathcache" not in sg_dict)



    def test_publish_errors(self):
        """Tests exceptions raised on publish errors."""

        # Try publishing with various wrong arguments and test the exceptions
        # being raised contain the PublishedEntity when it was created

        # Publish with an invalid Version, no PublishEntity should have been
        # created
        with self.assertRaises(tank.util.ShotgunPublishError) as cm:

            publish_data = tank.util.register_publish(
                self.tk,
                self.context,
                "bad_version",
                self.name,
                { "id" : -1, "type" : "Version" },
                dry_run=True
            )
            self.assertIsInstance(publish_data, dict)

            tank.util.register_publish(
                self.tk,
                self.context,
                "bad_version",
                self.name,
                { "id" : -1, "type" : "Version" }
            )
        self.assertIsNone(cm.exception.entity)

        # Force failure after the PublishedFile was created and check we get it
        # in the Exception last args.

        # Replace upload_thumbnail with a constant failure
        def raise_value_error(*arg, **kwargs):
            raise ValueError("Failed")
        with patch(
            "tank_vendor.shotgun_api3.lib.mockgun.Shotgun.upload_thumbnail",
            new=raise_value_error) as mock:
            with self.assertRaises(tank.util.ShotgunPublishError) as cm:

                publish_data = tank.util.register_publish(
                    self.tk,
                    self.context,
                    "Constant failure",
                    self.name,
                    self.version,
                    dependencies= [-1],
                    dry_run=True
                )
                self.assertIsInstance(publish_data, dict)

                tank.util.register_publish(
                    self.tk,
                    self.context,
                    "Constant failure",
                    self.name,
                    self.version,
                    dependencies= [-1]
                )
        self.assertIsInstance(cm.exception.entity, dict)
        self.assertTrue(cm.exception.entity["type"]==tank.util.get_published_file_entity_type(self.tk))

        # Replace upload_thumbnail with a constant IO error
        def raise_io_error(*arg, **kwargs):
            open("/this/file/does/not/exist/or/we/are/very/unlucky.txt", "r")
        with patch(
            "tank_vendor.shotgun_api3.lib.mockgun.Shotgun.upload_thumbnail",
            new=raise_io_error) as mock:
            with self.assertRaises(tank.util.ShotgunPublishError) as cm:

                publish_data = tank.util.register_publish(
                    self.tk,
                    self.context,
                    "dummy_path.txt",
                    self.name,
                    self.version,
                    dependencies=[-1],
                    dry_run=True
                )
                self.assertIsInstance(publish_data, dict)

                tank.util.register_publish(
                    self.tk,
                    self.context,
                    "dummy_path.txt",
                    self.name,
                    self.version,
                    dependencies= [-1]
                )
        self.assertIsInstance(cm.exception.entity, dict)
        self.assertTrue(cm.exception.entity["type"]==tank.util.get_published_file_entity_type(self.tk))


class TestCalcPathCache(TankTestBase):
    
    @patch("tank.pipelineconfig.PipelineConfiguration.get_data_roots")
    def test_case_difference(self, get_data_roots):
        """
        Case that root case is different between input path and that in roots file.
        Bug Ticket #18116
        """
        get_data_roots.return_value = {"primary" : self.project_root}
        
        relative_path = os.path.join("Some","Path")
        wrong_case_root = self.project_root.swapcase()
        expected = os.path.join(os.path.basename(wrong_case_root), relative_path).replace(os.sep, "/")

        input_path = os.path.join(wrong_case_root, relative_path)
        root_name, path_cache = tank.util.shotgun.publish_creation._calc_path_cache(self.tk, input_path)
        self.assertEqual("primary", root_name)
        self.assertEqual(expected, path_cache)


