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

from tank.util import EnvironmentVariableFileLookupError
from tank.util.user_settings import UserSettings


class MockConfigParser(object):
    """
    Mocks the config parser object used internally by the UserSettings class.
    """

    def __init__(self, data):
        """
        Constructor.
        """
        self._data = {
            "Login": data
        }

    def has_section(self, name):
        """
        Checks if a section [name] is present.
        """
        return name in self._data

    def has_option(self, name, key):
        """
        Checks for setting key: inside [name].
        """
        return self.has_section(name) and key in self._data[name]

    def get(self, name, key):
        """
        Retrieves setting from ini file.
        """
        return self._data[name][key]

    def read(self, path):
        """
        Mocked to please the UserSettings implementation.
        """
        pass


# Got get the tank test harness, we don't want part of the API mocked, we'll
# mock the parsing and be done with it.
class UserSettingsTests(unittest.TestCase):
    """
    Tests functionality around config.ini
    """

    def setUp(self):
        """
        Make sure the singleton is reset at the beginning of this test.
        """
        UserSettings.clear_singleton()
        self.addCleanup(UserSettings.clear_singleton)

    @patch("tank.util.user_settings.UserSettings._load_config", return_value=MockConfigParser({}))
    def test_empty_file(self, mock):
        """
        Tests a complete yaml file.
        """
        settings = UserSettings()
        self.assertIsNone(settings.default_site)
        self.assertIsNone(settings.default_login)
        self.assertIsNone(settings.shotgun_proxy)
        self.assertFalse(settings.is_app_store_proxy_set())

    @patch("tank.util.user_settings.UserSettings._load_config", return_value=MockConfigParser({
        "default_site": "site",
        "default_login": "login",
        "http_proxy": "http_proxy",
        "app_store_http_proxy": "app_store_http_proxy"
    }))
    def test_filled_file(self, mock):
        """
        Tests a complete yaml file.
        """
        settings = UserSettings()
        self.assertEqual(settings.default_site, "site")
        self.assertEqual(settings.default_login, "login")
        self.assertEqual(settings.shotgun_proxy, "http_proxy")
        self.assertTrue(settings.is_app_store_proxy_set())
        self.assertEqual(settings.app_store_proxy, "app_store_http_proxy")

    @patch("tank.util.user_settings.UserSettings._load_config", return_value=MockConfigParser({}))
    def test_system_proxy(self, mock):
        """
        Tests the fallback on the operating system http proxy.
        """
        http_proxy = "http://foo:bar@74.50.63.111:80"  # IP address of shotgunstudio.com

        with patch.dict(os.environ, {"http_proxy": http_proxy}):
            settings = UserSettings()
            self.assertEqual(settings.shotgun_proxy, http_proxy)

    @patch("tank.util.user_settings.UserSettings._load_config", return_value=MockConfigParser({
        # Config parser represent empty settings as empty strings
        "app_store_http_proxy": ""
    }))
    def test_app_store_to_none(self, mock):
        """
        Tests a file with a present but empty app store proxy setting.
        """
        settings = UserSettings()
        self.assertTrue(settings.is_app_store_proxy_set())
        self.assertEqual(settings.app_store_proxy, None)

    @patch("tank.util.user_settings.UserSettings._load_config", return_value=MockConfigParser({
        # Config parser represent empty settings as empty strings
        "default_site": "https://${SGTK_TEST_SHOTGUN_SITE}.shotgunstudio.com"
    }))
    def test_environment_variable_expansions(self, mock):
        """
        Tests that setting an environment variable will be resolved.
        """
        with patch.dict(os.environ, {"SGTK_TEST_SHOTGUN_SITE": "shotgun_site"}):
            settings = UserSettings()
            self.assertEqual(settings.default_site, "https://shotgun_site.shotgunstudio.com")

    def test_bad_environment_variable(self):
        """
        Test environment variables being set to files that don't exist.
        """
        with patch.dict(os.environ, {"SGTK_PREFERENCES_LOCATION": "/a/b/c"}):
            with self.assertRaisesRegexp(EnvironmentVariableFileLookupError, "/a/b/c"):
                UserSettings()

        with patch.dict(os.environ, {"SGTK_DESKTOP_CONFIG_LOCATION": "/d/e/f"}):
            with self.assertRaisesRegexp(EnvironmentVariableFileLookupError, "/d/e/f"):
                UserSettings()
