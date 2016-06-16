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
import datetime
import threading
import unittest2 as unittest

from mock import patch

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

        self.storage = {"type": "LocalStorage", "id": 1, "code": "Tank"}

        self.tank_type_1 = {"type": "TankType",
            "id": 1,
            "code": "Maya Scene"
        }

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.storage, self.tank_type_1])
        

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


