# Copyright (c) 2016 Shotgun Software Inc.
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

import unittest2 as unittest
from mock import patch

from tank import TankError
from tank.settings.core import CoreSettings

# Got get the tank test harness, we don't want part of the API mocked, we'll
# mock the yaml cache and be done with it.
class CoreSettingsTests(unittest.TestCase):

    def setUp(self):
        # Make sure we never try to resolve the shotgun.yml location, since we don't
        # want to trip on core throwing an exception because there's no pipeline
        # configuration. We don't need to actual do anything, simply stub it out.
        patcher = patch("tank.settings.core.CoreSettings.get_location", return_value=os.path.expanduser("~"))
        patcher.start()
        self.addCleanup(patcher.stop)

    @patch("tank.util.yaml_cache.g_yaml_cache.get", return_value={
        "api_key": "key",
        "api_script": "script",
        "http_proxy": "proxy",
        "app_store_http_proxy": "app_proxy",
        "host": "host"
    })
    def test_read_shotgun_yml(self, mock):
        """
        Tests a complete yaml file.
        """
        settings = CoreSettings()
        self.assertEqual(settings.api_key, "key")
        self.assertEqual(settings.api_script, "script")
        self.assertEqual(settings.http_proxy, "proxy")
        self.assertEqual(settings.app_store_http_proxy, "app_proxy")
        self.assertEqual(settings.host, "host")
        self.assertTrue(settings.is_script_user_configured())
        self.assertTrue(settings.is_app_store_http_proxy_set())

    @patch("tank.util.yaml_cache.g_yaml_cache.get", return_value={
        "User1": {
            "api_key": "key_User1",
            "api_script": "script_User1",
            "http_proxy": "proxy_User1",
            "app_store_http_proxy": "app_proxy_User1",
            "host": "host_User1"
        },
        "User2": {
            "api_key": "key_User2",
            "api_script": "script_User2",
            "http_proxy": "proxy_User2",
            "app_store_http_proxy": "app_proxy_User2",
            "host": "host_User2"
        }
    })
    def test_multi_user_shotgun_yml(self, mock):
        """
        Tests a shotgun.yml file with multiple users.
        """
        settings = CoreSettings("User2")
        self.assertEqual(settings.api_key, "key_User2")
        self.assertEqual(settings.api_script, "script_User2")
        self.assertEqual(settings.http_proxy, "proxy_User2")
        self.assertEqual(settings.app_store_http_proxy, "app_proxy_User2")
        self.assertEqual(settings.host, "host_User2")
        self.assertTrue(settings.is_script_user_configured())
        self.assertTrue(settings.is_app_store_http_proxy_set())

    @patch("tank.util.yaml_cache.g_yaml_cache.get", return_value={
        "User1": {
            "api_key": "key_User1",
            "api_script": "script_User1",
            "http_proxy": "proxy_User1",
            "app_store_http_proxy": "app_proxy_User1",
            "host": "host_User1"
        },
        "api_key": "key_unnamed",
        "api_script": "script_unnamed",
        "http_proxy": "proxy_unnamed",
        "app_store_http_proxy": "app_proxy_unnamed",
        "host": "host_unnamed"
    })
    def test_multi_user_shotgun_yml_fallback_on_unnamed_user(self, mock):
        """
        Tests a shotgun.yml file with multiple users, but requesting one
        that doesnt't exist.
        """
        settings = CoreSettings("ThisUserDoesntExist")
        self.assertEqual(settings.api_key, "key_unnamed")
        self.assertEqual(settings.api_script, "script_unnamed")
        self.assertEqual(settings.http_proxy, "proxy_unnamed")
        self.assertEqual(settings.app_store_http_proxy, "app_proxy_unnamed")
        self.assertEqual(settings.host, "host_unnamed")
        self.assertTrue(settings.is_script_user_configured())
        self.assertTrue(settings.is_app_store_http_proxy_set())

    @patch("tank.util.yaml_cache.g_yaml_cache.get", return_value={})
    def test_missing_host(self, mock):
        """
        Tests a shotgun.yml file with missing host.
        """
        with self.assertRaisesRegexp(TankError, "Missing required field 'host'"):
            settings = CoreSettings("SomeMissingUser")
        with self.assertRaisesRegexp(TankError, "Missing required field 'host'"):
            settings = CoreSettings()

    @patch("tank.util.yaml_cache.g_yaml_cache.get", return_value={"host": "host"})
    def test_missing_script(self, mock):
        """
        Tests a multi-user shotgun.yml file with missing script user.
        """
        with self.assertRaisesRegexp(TankError, "Missing required script user in config"):
            settings = CoreSettings("SomeMissingUser")


    @patch("tank.util.yaml_cache.g_yaml_cache.get", return_value={"host": "host"})
    def test_no_script_no_app_store_proxy(self, mock):
        """
        Tests a regular file with a single host field and nothing else.
        """
        settings = CoreSettings()
        self.assertIsNone(settings.api_key)
        self.assertIsNone(settings.api_script)
        self.assertIsNone(settings.http_proxy)
        self.assertIsNone(settings.app_store_http_proxy)
        self.assertEqual(settings.host, "host")
        self.assertFalse(settings.is_script_user_configured())
        self.assertFalse(settings.is_app_store_http_proxy_set())

    @patch("tank.util.yaml_cache.g_yaml_cache.get", return_value={
        "host": "host", "app_store_http_proxy": None
    })
    def test_none_app_store_proxy(self, mock):
        """
        Tests a shotgun.yml file with the app store proxy forced to be None.
        """
        settings = CoreSettings()
        self.assertIsNone(settings.api_key)
        self.assertTrue(settings.is_app_store_http_proxy_set())

    @patch("tank.util.yaml_cache.g_yaml_cache.get", return_value={"host": "host", "api_key": "key"})
    def test_half_configured_script_user(self, mock):
        """
        Tests a regular file with a single host field and nothing else.
        """
        with self.assertRaisesRegexp(TankError, "required field 'api_script'"):
            settings = CoreSettings()

        mock.return_value = {"host": "host", "api_script": "script"}

        with self.assertRaisesRegexp(TankError, "required field 'api_key'"):
            settings = CoreSettings()
