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
Tests settings retrieval from session_cache and config.ini
"""

from __future__ import with_statement
from mock import patch, Mock

from tank_test.tank_test_base import *

from tank.authentication import DefaultsManager
from tank.authentication import GlobalSettings


class DefaultsManagerTest(TankTestBase):
    """
    Tests the defaults manager.
    """

    _SESSION_CACHE_HOST = "https://session-cache.shotgunstudio.com"
    _CONFIG_HOST = "https://config-ini.shotgunstudio.com"

    _SESSION_CACHE_USER = "cached_user"
    _CONFIG_USER = "config_user"

    def setUp(self):
        """
        Sets up the next test's environment.
        """
        TankTestBase.setUp(self)
        GlobalSettings.reset_singleton()

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
        instance = GlobalSettings._instance = Mock()
        instance.default_http_proxy = None
        instance.default_site = self._CONFIG_HOST
        instance.default_login = self._CONFIG_USER
        instance.default_app_store_http_proxy = None

        dm = DefaultsManager()
        self.assertEqual(dm.get_host(), self._SESSION_CACHE_HOST)
        self.assertEqual(dm.get_login(), self._SESSION_CACHE_USER)
        self.assertIs(dm.get_http_proxy(), None)
