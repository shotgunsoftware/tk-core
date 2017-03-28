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


class TestShotgunFindPublish(TankTestBase):
    
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestShotgunFindPublish, self).setUp()
        
        #self.setup_fixtures()
        self.setup_multi_root_fixtures()
        
        project_name = os.path.basename(self.project_root)

        # older publish to test we get the latest
        self.pub_1 = {"type": "TankPublishedFile",
                    "id": 1,
                    "code": "hello",
                    "path_cache": "%s/foo/bar" % project_name,
                    "created_at": datetime.datetime(2012, 10, 12, 12, 1),
                    "path_cache_storage": self.primary_storage}

        # publish matching older publish
        self.pub_2 = {"type": "TankPublishedFile",
                    "id": 2,
                    "code": "more recent",
                    "path_cache": "%s/foo/bar" % project_name,
                    "created_at": datetime.datetime(2012, 10, 13, 12, 1),
                    "path_cache_storage": self.primary_storage}
        
        self.pub_3 = {"type": "TankPublishedFile",
                    "id": 3,
                    "code": "world",
                    "path_cache": "%s/foo/baz" % project_name,
                    "created_at": datetime.datetime(2012, 10, 13, 12, 2),
                    "path_cache_storage": self.primary_storage}

        # sequence publish
        self.pub_4 = {"type": "TankPublishedFile",
                    "id": 4,
                    "code": "sequence_file",
                    "path_cache": "%s/foo/seq_%%03d.ext" % project_name,
                    "created_at": datetime.datetime(2012, 10, 13, 12, 2),
                    "path_cache_storage": self.primary_storage}


        self.pub_5 = {"type": "TankPublishedFile",
                    "id": 5,
                    "code": "other storage",
                    "path_cache": "%s/foo/bar" % project_name,
                    "created_at": datetime.datetime(2012, 10, 12, 12, 1),
                    "path_cache_storage": self.alt_storage_1}

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.pub_1, self.pub_2, self.pub_3, self.pub_4, self.pub_5])
        
        

    def test_find(self):        
        paths = [os.path.join(self.project_root, "foo", "bar")]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), 1)
        self.assertEqual(d.keys(), paths)
        # make sure we got the latest matching publish
        sg_data = d.get(paths[0])
        self.assertEqual(sg_data["id"], self.pub_2["id"])
        self.assertEqual(sg_data["type"], "TankPublishedFile")
        # make sure we are only getting the ID back.
        self.assertEqual(sg_data.keys(), ["type", "id"])

    def test_most_recent_path(self):
        # check that dupes return the more recent record        
        paths = [os.path.join(self.project_root, "foo", "bar")]
        d = tank.util.find_publish(self.tk, paths, fields=["code"])
        self.assertEqual(len(d), 1)
        sg_data = d.get(paths[0])
        self.assertEqual(sg_data["code"], "more recent")

    def test_missing_paths(self):
        paths = [os.path.join(self.project_root, "foo", "bar"),
                 os.path.join("tmp", "foo")]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), 1)
        self.assertEqual(d.keys(), [ paths[0] ])

    def test_sequence_path(self):
        # make sequence template matching sequence publish
        keys = {"seq": SequenceKey("seq", format_spec="03")}
        template = TemplatePath("foo/seq_{seq}.ext", keys, self.project_root)
        self.tk.templates["sequence_test"] = template
        paths = [os.path.join(self.project_root, "foo", "seq_002.ext")]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), 1)
        self.assertEqual(d.keys(), [ paths[0] ])
        sg_data = d.get(paths[0])
        self.assertEqual(sg_data["id"], self.pub_4["id"])

    def test_abstracted_sequence_path(self):
        # make sequence template matching sequence publish
        keys = {"seq": SequenceKey("seq", format_spec="03")}
        template = TemplatePath("foo/seq_{seq}.ext", keys, self.project_root)
        self.tk.templates["sequence_test"] = template
        paths = [os.path.join(self.project_root, "foo", "seq_%03d.ext")]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), 1)
        self.assertEqual(d.keys(), [ paths[0] ])
        sg_data = d.get(paths[0])
        self.assertEqual(sg_data["id"], self.pub_4["id"])

    def test_multi_root(self):        
        paths = [os.path.join(self.alt_root_1, "foo", "bar")]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), 1)
        self.assertEqual(d.keys(), paths)
        
        # make sure we got the latest matching publish
        sg_data = d.get(paths[0])        
        self.assertEqual(sg_data["id"], self.pub_5["id"])
        
        # make sure we are only getting the ID back.
        self.assertEqual(sg_data.keys(), ["type", "id"])
        
    def test_ignore_missing(self):  
        """
        If a storage is not registered in shotgun, the path is ignored
        (previously it used to raise an error)
        """      
        paths = [os.path.join(self.project_root, "foo", "doesnotexist")]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), 0)

    def test_translate_abstract_fields(self):
        # We should get back what we gave since there won't be a matching
        # template for this path.
        self.assertEqual(
            "/jbee/is/awesome.0001.jpg",
            tank.util.shotgun._translate_abstract_fields(
                self.tk,
                "/jbee/is/awesome.0001.jpg",
            ),
        )

        # Build a set of matching templates.
        keys = dict(
            seq=tank.templatekey.SequenceKey(
                "seq",
                format_spec="03",
            ),
            frame=SequenceKey(
                "frame",
                format_spec="04",
            ),
        )
        template = TemplatePath(
            "folder/name_{seq}.{frame}.ext",
            keys,
            self.project_root,
        )
        dup_template = TemplatePath(
            "folder/name_{seq}.{frame}.ext",
            keys,
            self.project_root,
        )

        self.tk.templates["translate_fields_test"] = template

        # We should get back a transformed path since there's a single
        # matching template.
        path = os.path.join(self.project_root, "folder", "name_001.9999.ext")
        t_path = os.path.join(self.project_root, "folder", "name_%03d.%04d.ext")

        self.assertEqual(
            t_path,
            tank.util.shotgun._translate_abstract_fields(
                self.tk,
                path,
            ),
        )

        self.tk.templates["translate_fields_test_dup"] = dup_template

        # We should get back what we gave due to multiple matching templates.
        self.assertEqual(
            path,
            tank.util.shotgun._translate_abstract_fields(
                self.tk,
                path,
            ),
        )



class TestShotgunFindPublishTankStorage(TankTestBase):
    
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestShotgunFindPublishTankStorage, self).setUp()
        
        #self.setup_fixtures()
        self.setup_multi_root_fixtures()

        self.storage_2 = {"type": "LocalStorage", "id": 43, "code": "alternate_1"}
        
        project_name = os.path.basename(self.project_root)
        # older publish to test we get the latest
        self.pub_1 = {"type": "TankPublishedFile",
                    "id": 1,
                    "code": "hello",
                    "path_cache": "%s/foo/bar" % project_name,
                    "created_at": datetime.datetime(2012, 10, 12, 12, 1),
                    "path_cache_storage": self.primary_storage}

        # publish matching older publish
        self.pub_2 = {"type": "TankPublishedFile",
                    "id": 2,
                    "code": "more recent",
                    "path_cache": "%s/foo/bar" % project_name,
                    "created_at": datetime.datetime(2012, 10, 13, 12, 1),
                    "path_cache_storage": self.primary_storage}
        
        self.pub_3 = {"type": "TankPublishedFile",
                    "id": 3,
                    "code": "world",
                    "path_cache": "%s/foo/baz" % project_name,
                    "created_at": datetime.datetime(2012, 10, 13, 12, 2),
                    "path_cache_storage": self.primary_storage}

        # sequence publish
        self.pub_4 = {"type": "TankPublishedFile",
                    "id": 4,
                    "code": "sequence_file",
                    "path_cache": "%s/foo/seq_%%03d.ext" % project_name,
                    "created_at": datetime.datetime(2012, 10, 13, 12, 2),
                    "path_cache_storage": self.primary_storage}


        self.pub_5 = {"type": "TankPublishedFile",
                    "id": 5,
                    "code": "other storage",
                    "path_cache": "%s/foo/bar" % project_name,
                    "created_at": datetime.datetime(2012, 10, 12, 12, 1),
                    "path_cache_storage": self.alt_storage_1}

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.pub_1, self.pub_2, self.pub_3, self.pub_4, self.pub_5])
        

    def test_find(self):        
        paths = [os.path.join(self.project_root, "foo", "bar")]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), 1)
        self.assertEqual(d.keys(), paths)
        # make sure we got the latest matching publish
        sg_data = d.get(paths[0])
        self.assertEqual(sg_data["id"], self.pub_2["id"])
        self.assertEqual(sg_data["type"], "TankPublishedFile")
        # make sure we are only getting the ID back.
        self.assertEqual(sg_data.keys(), ["type", "id"])

    def test_most_recent_path(self):
        # check that dupes return the more recent record        
        paths = [os.path.join(self.project_root, "foo", "bar")]
        d = tank.util.find_publish(self.tk, paths, fields=["code"])
        self.assertEqual(len(d), 1)
        sg_data = d.get(paths[0])
        self.assertEqual(sg_data["code"], "more recent")

    def test_missing_paths(self):
        paths = [os.path.join(self.project_root, "foo", "bar"),
                 os.path.join("tmp", "foo")]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), 1)
        self.assertEqual(d.keys(), [ paths[0] ])

    def test_sequence_path(self):
        # make sequence template matching sequence publish
        keys = {"seq": SequenceKey("seq", format_spec="03")}
        template = TemplatePath("foo/seq_{seq}.ext", keys, self.project_root)
        self.tk.templates["sequence_test"] = template
        paths = [os.path.join(self.project_root, "foo", "seq_002.ext")]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), 1)
        self.assertEqual(d.keys(), [ paths[0] ])
        sg_data = d.get(paths[0])
        self.assertEqual(sg_data["id"], self.pub_4["id"])

    def test_abstracted_sequence_path(self):
        # make sequence template matching sequence publish
        keys = {"seq": SequenceKey("seq", format_spec="03")}
        template = TemplatePath("foo/seq_{seq}.ext", keys, self.project_root)
        self.tk.templates["sequence_test"] = template
        paths = [os.path.join(self.project_root, "foo", "seq_%03d.ext")]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), 1)
        self.assertEqual(d.keys(), [ paths[0] ])
        sg_data = d.get(paths[0])
        self.assertEqual(sg_data["id"], self.pub_4["id"])

    def test_multi_root(self):        
        paths = [os.path.join(self.alt_root_1, "foo", "bar")]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), 1)
        self.assertEqual(d.keys(), paths)
        # make sure we got the latest matching publish
        sg_data = d.get(paths[0])
        
        self.assertEqual(sg_data["id"], self.pub_5["id"])
        
        # make sure we are only getting the ID back.
        self.assertEqual(sg_data.keys(), ["type", "id"])






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

        self.tank_type_1 = {"type": "TankType",
            "id": 1,
            "code": "Maya Scene"
        }

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.storage, self.storage_2, self.storage_3, self.tank_type_1])

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
    def test_file_paths(self, create_mock):
        """
        Tests that we generate file:// paths when storage is not found
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
    def test_freeform_local_storage_paths(self, create_mock):
        """
        Tests that we generate local file links for storages
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

class TestShotgunDownloadUrl(TankTestBase):

    def setUp(self):
        super(TestShotgunDownloadUrl, self).setUp()

        self.setup_fixtures()

        # Identify the source file to "download"
        self.download_source = os.path.join(
            self.pipeline_config_root, "config", "hooks", "toolkitty.png"
        )

        # Construct a URL from the source file name
        self.download_url = urlparse.urlunparse(
            ("file", None, self.download_source, None, None, None)
        )

        # Temporary destination to "download" source file to.
        self.download_destination = os.path.join(
            self.pipeline_config_root, "config", "foo",
            "test_shotgun_download_url.png"
        )
        os.makedirs(os.path.dirname(self.download_destination))
        if os.path.exists(self.download_destination):
            os.remove(self.download_destination)

        # Make sure mockgun is properly configured
        if self.mockgun.config.server is None:
            self.mockgun.config.server = "unit_test_mock_sg"

    def tearDown(self):
        if os.path.exists(self.download_destination):
            os.remove(self.download_destination)

        # important to call base class so it can clean up memory
        super(TestShotgunDownloadUrl, self).tearDown()

    def test_download(self):
        """
        Verify URL can be downloaded to specified path.
        """
        # Verify the download destination file does not exist.
        if os.path.exists(self.download_destination):
            os.remove(self.download_destination)
        self.assertFalse(os.path.exists(self.download_destination))

        # Attempt to download url and capture the downloaded file name.
        downloaded_to = tank.util.download_url(
            self.mockgun, self.download_url, self.download_destination
        )

        # Verify the destination file exists and is the same as
        # the return value from tank.util.download_url()
        self.assertTrue(os.path.exists(self.download_destination))
        self.assertEqual(self.download_destination, downloaded_to)

    def test_use_url_extension(self):
        """
        Verify correct exension gets extracted from the input
        url and appended to the input location value on return.
        """
        # Remove the file extension from the download destination
        path_base = os.path.splitext(self.download_destination)[0]

        # Ask tank.util.download_url() to append the exension from the
        # resolved URL to the input destination location and capture
        # the full path return value.
        full_path = tank.util.download_url(
            self.mockgun, self.download_url, path_base, True
        )

        # Verify the return value is different than the input value
        self.assertNotEqual(path_base, full_path)

        # Verify the correct file extension was returned.
        self.assertEqual(self.download_destination, full_path)


class TestGetSgConfigData(TankTestBase):

    def _prepare_common_mocks(self, get_api_core_config_location_mock):
        get_api_core_config_location_mock.return_value = "unknown_path_location"

    def test_all_fields_present(self, get_api_core_config_location_mock):
        self._prepare_common_mocks(get_api_core_config_location_mock)
        tank.util.shotgun._parse_config_data(
            {
                "host": "host",
                "api_key": "api_key",
                "api_script": "api_script",
                "http_proxy": "http_proxy"
            },
            "default",
            "not_a_file.cfg"
        )

    def test_proxy_is_optional(self, get_api_core_config_location_mock):
        self._prepare_common_mocks(get_api_core_config_location_mock)
        tank.util.shotgun._parse_config_data(
            {
                "host": "host",
                "api_key": "api_key",
                "api_script": "api_script"
            },
            "default",
            "not_a_file.cfg"
        )

    def test_incomplete_script_user_credentials(self, get_api_core_config_location_mock):
        self._prepare_common_mocks(get_api_core_config_location_mock)

        with self.assertRaises(errors.TankError):
            tank.util.shotgun._parse_config_data(
                {
                    "host": "host",
                    "api_script": "api_script"
                },
                "default",
                "not_a_file.cfg"
            )

        with self.assertRaises(errors.TankError):
            tank.util.shotgun._parse_config_data(
                {
                    "host": "host",
                    "api_key": "api_key"
                },
                "default",
                "not_a_file.cfg"
            )

        with self.assertRaises(errors.TankError):
            tank.util.shotgun._parse_config_data(
                {
                    "api_key": "api_key",
                    "api_script": "api_script"
                },
                "default",
                "not_a_file.cfg"
            )

# Class decorators don't exist on Python2.5
TestGetSgConfigData = patch("tank.util.shotgun.__get_api_core_config_location", TestGetSgConfigData)


class ConnectionSettingsTestCases:
    """
    Avoid multiple inheritance in the tests by scoping this test so the test runner
    doesn't see it.
    http://stackoverflow.com/a/25695512
    """

    FOLLOW_HTTP_PROXY_SETTING = "FOLLOW_HTTP_PROXY_SETTING"

    class Impl(unittest.TestCase):
        """
        Test cases for connection validation.
        """

        _SITE = "https://127.0.0.1"
        _SITE_PROXY = "127.0.0.2"
        _STORE_PROXY = "127.0.0.3"

        def setUp(self):
            """
            Clear cached appstore connection
            """
            tank.util.shotgun._g_sg_cached_connections = threading.local()
            tank.set_authenticated_user(None)

            # Prevents from connecting to Shotgun.
            self._server_caps_mock = patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
            self._server_caps_mock.start()
            self.addCleanup(self._server_caps_mock.stop)

            # Avoids crash because we're not in a pipeline configuration.
            self._get_api_core_config_location_mock = patch(
                "tank.util.shotgun.__get_api_core_config_location",
                return_value="unused_path_location"
            )
            self._get_api_core_config_location_mock.start()
            self.addCleanup(self._get_api_core_config_location_mock.stop)

            # Mocks app store script user credentials retrieval
            self._get_app_store_key_from_shotgun_mock = patch(
                "tank.descriptor.io_descriptor.appstore.IODescriptorAppStore._IODescriptorAppStore__get_app_store_key_from_shotgun",
                return_value=("abc", "123")
            )
            self._get_app_store_key_from_shotgun_mock.start()
            self.addCleanup(self._get_app_store_key_from_shotgun_mock.stop)

        def tearDown(self):
            """
            Clear cached appstore connection
            """
            tank.util.shotgun._g_sg_cached_connections = threading.local()
            tank.set_authenticated_user(None)

        def test_connections_no_proxy(self):
            """
            No proxies set, so everything should be None.
            """
            self._run_test(site=self._SITE)

        def test_connections_site_proxy(self):
            """
            When the http_proxy setting is set in shotgun.yml, both the site
            connection and app store connections are expected to use the
            proxy setting.
            """
            self._run_test(
                site=self._SITE,
                source_proxy=self._SITE_PROXY,
                expected_store_proxy=self._SITE_PROXY
            )

        def test_connections_store_proxy(self):
            """
            When the app_store_http_proxy setting is set in shotgun.yml, the app
            store connections are expected to use the proxy setting.
            """
            self._run_test(
                site=self._SITE,
                source_proxy=self._SITE_PROXY,
                expected_store_proxy=self._SITE_PROXY
            )

        def test_connections_both_proxy(self):
            """
            When both proxy settings are set, each connection has its own proxy.
            """
            self._run_test(
                site=self._SITE,
                source_proxy=self._SITE_PROXY,
                source_store_proxy=self._STORE_PROXY,
                expected_store_proxy=self._STORE_PROXY
            )

        def test_connections_site_proxy_and_no_appstore_proxy(self):
            """
            When the source store proxy is set to None in shotgun.yml, we are forcing it
            to be empty and now use the value from the site setting.
            """
            self._run_test(
                site=self._SITE,
                source_proxy=self._SITE_PROXY,
                source_store_proxy=None,
                expected_store_proxy=None
            )

        def _run_test(self, site, source_proxy, source_store_proxy, expected_store_proxy):
            """
            Should be implemented by derived classes in order to mock authentication
            for the test.

            :param site: Site used for authentication
            :param source_proxy: proxy being returned by the authentication code for the site
            :param source_store_proxy: proxy being return by the authentication for the app store.
            :param expected_store_proxy: actual proxy value
            """
            # Make sure that the site uses the host and proxy.
            sg = tank.util.shotgun.create_sg_connection()
            self.assertEqual(sg.base_url, self._SITE)
            self.assertEqual(sg.config.raw_http_proxy, source_proxy)

            descriptor = IODescriptorAppStore(
                {"name": "tk-multi-app", "version": "v0.0.1", "type": "app_store"},
                sg, Descriptor.CORE
            )
            http_proxy = descriptor._IODescriptorAppStore__get_app_store_proxy_setting()
            self.assertEqual(http_proxy, expected_store_proxy)


class LegacyAuthConnectionSettings(ConnectionSettingsTestCases.Impl):
    """
    Tests proxy connection for site and appstore connections.
    """

    def _run_test(
        self,
        site,
        source_proxy=None,
        source_store_proxy=ConnectionSettingsTestCases.FOLLOW_HTTP_PROXY_SETTING,
        expected_store_proxy=None
    ):
        """
        Mock information coming from shotgun.yml for pre-authentication framework authentication.
        """
        with patch("tank.util.shotgun.__get_sg_config_data") as mock:
            # Mocks shotgun.yml content, which we use for authentication.
            mock.return_value = {
                "host": site,
                "api_script": "1234",
                "api_key": "1234",
                "http_proxy": source_proxy
            }
            # Adds the app store proxy setting in the mock shotgun.yml settings if one should be present.
            if source_store_proxy != ConnectionSettingsTestCases.FOLLOW_HTTP_PROXY_SETTING:
                mock.return_value["app_store_http_proxy"] = source_store_proxy

            ConnectionSettingsTestCases.Impl._run_test(
                self,
                site=site,
                source_proxy=source_proxy,
                source_store_proxy=source_store_proxy,
                expected_store_proxy=expected_store_proxy
            )


class AuthConnectionSettings(ConnectionSettingsTestCases.Impl):
    """
    Tests proxy connection for site and appstore connections.
    """

    def _run_test(
        self,
        site,
        source_proxy=None,
        source_store_proxy=ConnectionSettingsTestCases.FOLLOW_HTTP_PROXY_SETTING,
        expected_store_proxy=None
    ):
        """
        Mock information coming from the Shotgun user and shotgun.yml for authentication.
        """
        with patch("tank.util.shotgun.__get_sg_config_data") as mock:
            # Mocks shotgun.yml content
            mock.return_value = {
                # We're supposed to read only the proxy settings for the appstore
                "host": "https://this_should_not_be_read.shotgunstudio.com",
                "api_script": "1234",
                "api_key": "1234",
                "http_proxy": "123.234.345.456:7890"
            }
            # Adds the app store proxy setting in the mock shotgun.yml settings if one should be present.
            if source_store_proxy != ConnectionSettingsTestCases.FOLLOW_HTTP_PROXY_SETTING:
                mock.return_value["app_store_http_proxy"] = source_store_proxy

            # Mocks a user being authenticated.
            user = ShotgunUser(
                SessionUser(
                    login="test_user", session_token="abc1234",
                    host=site, http_proxy=source_proxy
                )
            )
            tank.set_authenticated_user(user)

            ConnectionSettingsTestCases.Impl._run_test(
                self,
                site=site,
                source_proxy=source_proxy,
                source_store_proxy=source_store_proxy,
                expected_store_proxy=expected_store_proxy
            )


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
        root_name, path_cache = tank.util.shotgun._calc_path_cache(self.tk, input_path)
        self.assertEqual("primary", root_name)
        self.assertEqual(expected, path_cache)


