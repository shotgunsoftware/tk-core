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

from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
)

from tank_test.tank_test_base import setUpModule  # noqa

from tank.authentication import CoreDefaultsManager
from tank.authentication import DefaultsManager
from tank.util.user_settings import UserSettings
import sgtk


class DefaultsManagerTest(ShotgunTestBase):
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
        pass
    @mock.patch(
        "tank.authentication.session_cache.get_current_host",
        return_value=_SESSION_CACHE_HOST,
    )
    @mock.patch(
        "tank.authentication.session_cache.get_current_user",
        return_value=_SESSION_CACHE_USER,
    )
    def test_no_settings(self, *unused_mocks):
        pass
    def test_with_system_settings(self, *unused_mocks):
        pass
    @mock.patch("tank.authentication.session_cache.get_current_host", return_value=None)
    @mock.patch("tank.authentication.session_cache.get_current_user", return_value=None)
    def test_empty_session_cache(self, *unused_mocks):
        pass
    @mock.patch(
        "tank.util.shotgun.get_associated_sg_config_data",
        return_value={"host": _SHOTGUN_YML_HOST, "http_proxy": _SHOTGUN_YML_PROXY},
    )
    def test_shotgun_yml_over_global(self, *unused_mocks):
        pass
    @mock.patch(
        "tank.util.shotgun.get_associated_sg_config_data",
        return_value={"host": _SHOTGUN_YML_HOST},
    )
    def test_shotgun_yml_no_proxy_uses_global_proxy(self, *unused_mocks):
        pass
    @mock.patch(
        "tank.util.system_settings.SystemSettings.http_proxy",
        new_callable=mock.PropertyMock,
        return_value="192.168.10.1",
    )
    @mock.patch("tank.util.shotgun.get_associated_sg_config_data", return_value={})
    def test_toolkit_ini_disabling_global_proxy(self, *_):
        pass
    @mock.patch(
        "tank.util.shotgun.get_associated_sg_config_data",
        return_value={"http_proxy": ""},
    )
    @mock.patch(
        "tank.util.system_settings.SystemSettings.http_proxy",
        new_callable=mock.PropertyMock,
        return_value="192.168.10.1",
    )
    def test_shotgun_yml_empty_string_can_override_global_proxy(self, *_):
        pass
    def test_backwards_compatible(self):
        pass
    @mock.patch(
        "tank.authentication.session_cache.get_current_host",
        return_value=_SESSION_CACHE_HOST,
    )
    def test_fixed_host_on_init_overrides_everything(self, _):
        pass
