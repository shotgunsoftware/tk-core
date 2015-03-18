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

from mock import patch

import tank
from tank import context, errors
from tank import TankAuthenticationError
from tank_test.tank_test_base import *
from tank_test import mockgun
from tank.template import TemplatePath
from tank.templatekey import SequenceKey
from tank_vendor.shotgun_authentication import connection, errors as auth_errors


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


@patch("tank.util.shotgun.__get_api_core_config_location")
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


class TestCreateSessionBasedConnection(TankTestBase):
    """
    Tests the creation of a session based Shotgun connection.
    """

    @patch("tank_vendor.shotgun_authentication.authentication.get_connection_information")
    @patch("tank_vendor.shotgun_authentication.connection._create_or_renew_sg_connection_from_session")
    def test_no_script_user_uses_human_user(
        self,
        create_or_renew_sg_connection_from_session_mock,
        get_connection_information_mock
    ):
        """
        Makes sure having no user configured in shotgun.yml will invoke the
        _create_or_renew_sg_connection_from_session function.
        """
        config_data = {
            "host": "https://something.shotgunstudio.com"
        }
        get_connection_information_mock.return_value = config_data
        create_or_renew_sg_connection_from_session_mock.return_value = mockgun.Shotgun(
            config_data["host"]
        )

        # Make sure the engine is None otherwise failing to authenticate (something.shotgunstudio.com doesn't exist)
        # would trigger ui prompts.
        self.assertIsNone(tank.platform.engine.current_engine())
        # Because the credentials are invalid and there is no engine, no connection can be created.
        connection.create_authenticated_sg_connection()
        # Make sure there was an attempt to authenticate using cache session info.
        self.assertEqual(create_or_renew_sg_connection_from_session_mock.call_count, 1)

    @patch("tank_vendor.shotgun_authentication.connection.create_sg_connection_from_session")
    @patch("tank_vendor.shotgun_authentication.connection._renew_session")
    def test_create_connection_with_session_renewal(self, renew_session_mock, create_sg_connection_from_session_mock):
        """
        When there is no valid session cached, the engine's renew session should take care of the
        session renewal
        """

        new_connection = mockgun.Shotgun("https://something.shotgunstudio.com")
        # First call will fail creating something from the cache, and the second call will be the 
        # after we renwed the session.
        create_sg_connection_from_session_mock.side_effect = [None, new_connection]
        renew_session_mock.return_value = None

        result = connection._create_or_renew_sg_connection_from_session(
            "unused"
        )

        # Make sure we tried to renew the sesion
        self.assertTrue(renew_session_mock.called)
        self.assertEqual(create_sg_connection_from_session_mock.call_count, 2)
        self.assertEqual(id(result), id(new_connection))

    @patch("tank_vendor.shotgun_authentication.connection.create_sg_connection_from_session")
    @patch("tank_vendor.shotgun_authentication.connection._renew_session")
    def test_create_connection_with_session_renewal_failure(self, renew_session_mock, create_sg_connection_from_session_mock):
        """
        When there is no valid session cached, the engine's renew session should take care of the
        session renewal, but if the session renewal failed, we should get a TankAuthenticationError
        """
        # Always fail creating a cached session
        create_sg_connection_from_session_mock.return_value = None
        renew_session_mock.return_value = None

        with self.assertRaisesRegexp(auth_errors.AuthenticationError, "failed"):
            connection._create_or_renew_sg_connection_from_session("unused")
        # Make sure we tried to renew the sesion
        self.assertTrue(renew_session_mock.called)
        self.assertEqual(create_sg_connection_from_session_mock.call_count, 2)
