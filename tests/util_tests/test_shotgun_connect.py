# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import threading
import unittest

import tank
from tank import errors

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
    temp_env_var,
)
from tank.authentication.user import ShotgunUser
from tank.authentication.user_impl import SessionUser
from tank.descriptor import Descriptor
from tank.descriptor.io_descriptor.appstore import IODescriptorAppStore
from tank.util.shotgun.connection import sanitize_url


@mock.patch(
    "tank.util.shotgun.connection.__get_api_core_config_location",
    return_value="unknown_path_location",
)
class TestGetSgConfigData(ShotgunTestBase):
    def test_all_fields_present(self, get_api_core_config_location_mock):
        pass
    def test_env_vars_present(self, get_api_core_config_location_mock):
        pass
    def test_proxy_is_optional(self, get_api_core_config_location_mock):
        pass
    def test_incomplete_script_user_credentials(
        pass
    ):
        with self.assertRaises(errors.TankError):
            tank.util.shotgun.connection._parse_config_data(
                {"host": "host", "api_script": "api_script"},
                "default",
                "not_a_file.cfg",
            )

        with self.assertRaises(errors.TankError):
            tank.util.shotgun.connection._parse_config_data(
                {"host": "host", "api_key": "api_key"}, "default", "not_a_file.cfg"
            )

        with self.assertRaises(errors.TankError):
            tank.util.shotgun.connection._parse_config_data(
                {"api_key": "api_key", "api_script": "api_script"},
                "default",
                "not_a_file.cfg",
            )

    def test_parse_config_data_cleans_host(self, get_api_core_config_location_mock):
        pass
    def test_sanitize_url(self, get_api_core_config_location_mock):
        pass
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
            pass
        def tearDown(self):
            pass
        def test_connections_no_proxy(self):
            pass
        def test_connections_site_proxy(self):
            pass
        def test_connections_store_proxy(self):
            pass
        def test_connections_both_proxy(self):
            pass
        def test_connections_site_proxy_and_no_appstore_proxy(self):
            pass
        def _run_test(
            self, site, source_proxy, source_store_proxy, expected_store_proxy
        ):
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
                sg,
                Descriptor.CORE,
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
        expected_store_proxy=None,
    ):
        """
        Mock information coming from shotgun.yml for pre-authentication framework authentication.
        """
        with mock.patch("tank.util.shotgun.connection.__get_sg_config_data") as mock1:
            # Mocks shotgun.yml content, which we use for authentication.
            mock1.return_value = {
                "host": site,
                "api_script": "1234",
                "api_key": "1234",
                "http_proxy": source_proxy,
            }
            # Adds the app store proxy setting in the mock shotgun.yml settings if one should be present.
            if (
                source_store_proxy
                != ConnectionSettingsTestCases.FOLLOW_HTTP_PROXY_SETTING
            ):
                mock1.return_value["app_store_http_proxy"] = source_store_proxy

            ConnectionSettingsTestCases.Impl._run_test(
                self,
                site=site,
                source_proxy=source_proxy,
                source_store_proxy=source_store_proxy,
                expected_store_proxy=expected_store_proxy,
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
        expected_store_proxy=None,
    ):
        """
        Mock information coming from the Shotgun user and shotgun.yml for authentication.
        """
        with mock.patch("tank.util.shotgun.connection.__get_sg_config_data") as mock1:
            # Mocks shotgun.yml content
            mock1.return_value = {
                # We're supposed to read only the proxy settings for the appstore
                "host": "https://this_should_not_be_read.shotgunstudio.com",
                "api_script": "1234",
                "api_key": "1234",
                "http_proxy": "123.234.345.456:7890",
            }
            # Adds the app store proxy setting in the mock shotgun.yml settings if one should be present.
            if (
                source_store_proxy
                != ConnectionSettingsTestCases.FOLLOW_HTTP_PROXY_SETTING
            ):
                mock1.return_value["app_store_http_proxy"] = source_store_proxy

            # Mocks a user being authenticated.
            user = ShotgunUser(
                SessionUser(
                    login="test_user",
                    session_token="abc1234",
                    host=site,
                    http_proxy=source_proxy,
                )
            )
            tank.set_authenticated_user(user)

            ConnectionSettingsTestCases.Impl._run_test(
                self,
                site=site,
                source_proxy=source_proxy,
                source_store_proxy=source_store_proxy,
                expected_store_proxy=expected_store_proxy,
            )
