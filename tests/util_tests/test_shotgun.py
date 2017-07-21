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
        self.pub_1 = {"type": "PublishedFile",
                    "id": 1,
                    "code": "hello",
                    "path_cache": "%s/foo/bar" % project_name,
                    "created_at": datetime.datetime(2012, 10, 12, 12, 1),
                    "path_cache_storage": self.primary_storage}

        # publish matching older publish
        self.pub_2 = {"type": "PublishedFile",
                    "id": 2,
                    "code": "more recent",
                    "path_cache": "%s/foo/bar" % project_name,
                    "created_at": datetime.datetime(2012, 10, 13, 12, 1),
                    "path_cache_storage": self.primary_storage}
        
        self.pub_3 = {"type": "PublishedFile",
                    "id": 3,
                    "code": "world",
                    "path_cache": "%s/foo/baz" % project_name,
                    "created_at": datetime.datetime(2012, 10, 13, 12, 2),
                    "path_cache_storage": self.primary_storage}

        # sequence publish
        self.pub_4 = {"type": "PublishedFile",
                    "id": 4,
                    "code": "sequence_file",
                    "path_cache": "%s/foo/seq_%%03d.ext" % project_name,
                    "created_at": datetime.datetime(2012, 10, 13, 12, 2),
                    "path_cache_storage": self.primary_storage}

        self.pub_5 = {"type": "PublishedFile",
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
        self.assertEqual(sg_data["type"], "PublishedFile")
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
            tank.util.shotgun.publish_creation._translate_abstract_fields(
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
            tank.util.shotgun.publish_creation._translate_abstract_fields(
                self.tk,
                path,
            ),
        )

        self.tk.templates["translate_fields_test_dup"] = dup_template

        # We should get back what we gave due to multiple matching templates.
        self.assertEqual(
            path,
            tank.util.shotgun.publish_creation._translate_abstract_fields(
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
        self.pub_1 = {"type": "PublishedFile",
                    "id": 1,
                    "code": "hello",
                    "path_cache": "%s/foo/bar" % project_name,
                    "created_at": datetime.datetime(2012, 10, 12, 12, 1),
                    "path_cache_storage": self.primary_storage}

        # publish matching older publish
        self.pub_2 = {"type": "PublishedFile",
                    "id": 2,
                    "code": "more recent",
                    "path_cache": "%s/foo/bar" % project_name,
                    "created_at": datetime.datetime(2012, 10, 13, 12, 1),
                    "path_cache_storage": self.primary_storage}
        
        self.pub_3 = {"type": "PublishedFile",
                    "id": 3,
                    "code": "world",
                    "path_cache": "%s/foo/baz" % project_name,
                    "created_at": datetime.datetime(2012, 10, 13, 12, 2),
                    "path_cache_storage": self.primary_storage}

        # sequence publish
        self.pub_4 = {"type": "PublishedFile",
                    "id": 4,
                    "code": "sequence_file",
                    "path_cache": "%s/foo/seq_%%03d.ext" % project_name,
                    "created_at": datetime.datetime(2012, 10, 13, 12, 2),
                    "path_cache_storage": self.primary_storage}

        self.pub_5 = {"type": "PublishedFile",
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
        self.assertEqual(sg_data["type"], "PublishedFile")
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



