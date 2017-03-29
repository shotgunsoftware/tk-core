# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Tests settings retrieval through the DefaultsManager
"""

from __future__ import with_statement
from mock import patch, Mock

from tank_test.tank_test_base import *

from tank.util import CoreDefaultsManager
from tank.authentication import DefaultsManager
from tank.util.user_settings import UserSettings


class DefaultsManagerTest(TankTestBase):
    """
    Tests the defaults manager.
    """

    _SESSION_CACHE_HOST = "https://session-cache.shotgunstudio.com"
    _CONFIG_HOST = "https://config-ini.shotgunstudio.com"

    _SESSION_CACHE_USER = "cached_user"
    _CONFIG_USER = "config_user"

    _CONFIG_HTTP_PROXY = "config:proxy@192.168.1.1"
    _CONFIG_STORE_HTTP_PROXY = "config:app_proxy@192.168.1.1"

    _SHOTGUN_YML_HOST = "https//something.shotgunstudio.com"
    _SHOTGUN_YML_PROXY = "shotgun:yml@192.168.1.1"

    def setUp(self):
        """
        Sets up the next test's environment.
        """
        TankTestBase.setUp(self)
        UserSettings.clear_singleton()

    @patch(
        "tank.authentication.session_cache.get_current_host",
        return_value=_SESSION_CACHE_HOST
    )
    @patch(
        "tank.authentication.session_cache.get_current_user",
        return_value=_SESSION_CACHE_USER
    )
    def test_no_global_settings(self, *unused_mocks):
        """
        Test the behaviour of the defaults manager when there are no global settings.
        """
        instance = UserSettings._instance = Mock()
        instance.shotgun_proxy = None
        instance.default_site = self._CONFIG_HOST
        instance.default_login = self._CONFIG_USER
        instance.app_store_proxy = None

        dm = DefaultsManager()
        self.assertEqual(dm.get_host(), self._SESSION_CACHE_HOST)
        self.assertEqual(dm.get_login(), self._SESSION_CACHE_USER)
        self.assertIs(dm.get_http_proxy(), None)

    @patch(
        "tank.authentication.session_cache.get_current_host",
        return_value=None
    )
    @patch(
        "tank.authentication.session_cache.get_current_user",
        return_value=None
    )
    def test_empty_session_cache(self, *unused_mocks):
        """
        Test the behaviour of the defaults manager when the cache is empty
        and the config file is set.
        """
        instance = UserSettings._instance = Mock()
        instance.shotgun_proxy = self._CONFIG_HTTP_PROXY
        instance.default_site = self._CONFIG_HOST
        instance.default_login = self._CONFIG_USER

        dm = DefaultsManager()
        self.assertEqual(dm.get_host(), self._CONFIG_HOST)
        self.assertEqual(dm.get_login(), self._CONFIG_USER)
        self.assertIs(dm.get_http_proxy(), self._CONFIG_HTTP_PROXY)

    @patch(
        "tank.util.shotgun.get_associated_sg_config_data",
        return_value={
            "host": _SHOTGUN_YML_HOST,
            "http_proxy": _SHOTGUN_YML_PROXY
        }
    )
    def test_shotgun_yml_over_global(self, *unused_mocks):
        """
        Make sure that shotgun.yml always overrides config.ini
        """
        instance = UserSettings._instance = Mock()
        instance.shotgun_proxy = self._CONFIG_HTTP_PROXY
        instance.default_site = self._CONFIG_HOST
        instance.default_login = self._CONFIG_USER

        dm = CoreDefaultsManager()
        self.assertEqual(dm.get_host(), self._SHOTGUN_YML_HOST)
        self.assertEqual(dm.get_login(), self._CONFIG_USER)
        self.assertIs(dm.get_http_proxy(), self._SHOTGUN_YML_PROXY)

    @patch(
        "tank.util.shotgun.get_associated_sg_config_data",
        return_value={
            "host": _SHOTGUN_YML_HOST
        }
    )
    def test_shotgun_yml_no_proxy_uses_global_proxy(self, *unused_mocks):
        """
        Make sure that no proxy in shogun.yml means proxy in shotgun.yml will be picked.
        """
        instance = UserSettings._instance = Mock()
        instance.shotgun_proxy = self._CONFIG_HTTP_PROXY

        dm = CoreDefaultsManager()
        self.assertIs(dm.get_http_proxy(), self._CONFIG_HTTP_PROXY)

