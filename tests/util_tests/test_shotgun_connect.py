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
        """
        Ensures files with all settings are parsed correctly.
        """
        self.assertEqual(
            tank.util.shotgun.connection._parse_config_data(
                {
                    "host": "https://host.shotgunstudio.com",
                    "api_key": "api_key",
                    "api_script": "api_script",
                    "http_proxy": "http_proxy",
                },
                "default",
                "not_a_file.cfg",
            ),
            {
                "host": "https://host.shotgunstudio.com",
                "api_key": "api_key",
                "api_script": "api_script",
                "http_proxy": "http_proxy",
            },
        )

    def test_env_vars_present(self, get_api_core_config_location_mock):
        """
        Ensures files using environment variables are translated properly.
        """
        test_host = "https://envvar.shotgunstudio.com"
        test_key = "env_var_key"
        test_script = "env_var_script"
        test_proxy = "env_var_proxy"
        test_appstore_proxy = "env_var_appstore_proxy"

        with temp_env_var(
            SGTK_TEST_HOST=test_host,
            SGTK_TEST_KEY=test_key,
            SGTK_TEST_SCRIPT=test_script,
            SGTK_TEST_PROXY=test_proxy,
            SGTK_TEST_APPSTORE_PROXY=test_appstore_proxy,
        ):
            self.assertEqual(
                tank.util.shotgun.connection._parse_config_data(
                    {
                        "host": "$SGTK_TEST_HOST",
                        "api_key": "$SGTK_TEST_KEY",
                        "api_script": "$SGTK_TEST_SCRIPT",
                        "http_proxy": "$SGTK_TEST_PROXY",
                        "app_store_http_proxy": "$SGTK_TEST_APPSTORE_PROXY",
                    },
                    "default",
                    "not_a_file.cfg",
                ),
                {
                    "host": test_host,
                    "api_key": test_key,
                    "api_script": test_script,
                    "http_proxy": test_proxy,
                    "app_store_http_proxy": test_appstore_proxy,
                },
            )

    def test_proxy_is_optional(self, get_api_core_config_location_mock):
        tank.util.shotgun.connection._parse_config_data(
            {"host": "host", "api_key": "api_key", "api_script": "api_script"},
            "default",
            "not_a_file.cfg",
        )

    def test_incomplete_script_user_credentials(
        self, get_api_core_config_location_mock
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
        """
        Ensures shotgun.yml exposes a cleaned-up version of the host.
        """
        self.assertDictEqual(
            tank.util.shotgun.connection._parse_config_data(
                {"host": "https://extra.slash.will.be.removed/"},
                "default",
                "not_a_file.cfg",
            ),
            {"host": "https://extra.slash.will.be.removed"},
        )

    def test_sanitize_url(self, get_api_core_config_location_mock):
        """
        Ensures host is cleaned-up properly.
        """
        # Ensure https is added if no scheme is specified.
        self.assertEqual("https://no.scheme.com", sanitize_url("no.scheme.com"))

        # Ensure that we lowercase the URL.
        self.assertEqual("https://caps.site.com", sanitize_url("https://CAPS.site.com"))

        # Ensure https is not modified if specified.
        self.assertEqual("https://no.scheme.com", sanitize_url("https://no.scheme.com"))

        # Ensure http is left as is if specified.
        self.assertEqual("http://no.scheme.com", sanitize_url("http://no.scheme.com"))

        # Ensure any scheme is left as is if specified.
        self.assertEqual(
            "invalid-scheme://no.scheme.com",
            sanitize_url("invalid-scheme://no.scheme.com"),
        )

        # Ensures a suffixed slash gets removed.
        self.assertEqual(
            "https://no.suffixed.slash.com",
            sanitize_url("https://no.suffixed.slash.com/"),
        )

        # Ensures anything after the host is dropped.
        self.assertEqual(
            "https://no.suffixed.slash.com",
            sanitize_url("https://no.suffixed.slash.com/path/to/a/resource"),
        )

        # Ensures anything after the host is dropped.
        self.assertEqual("http://localhost", sanitize_url("http://localhost"))

        self.assertEqual("https://localhost", sanitize_url("localhost"))

        self.assertEqual("https://127.0.0.1", sanitize_url("127.0.0.1"))

        self.assertEqual(
            "https://test.shotgunstudio.com", sanitize_url("test.shotgunstudio.com/")
        )

        self.assertEqual(
            "https://test.shotgunstudio.com", sanitize_url("test.shotgunstudio.com/a")
        )


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
            tank.util.shotgun.connection._g_sg_cached_connections = threading.local()
            tank.set_authenticated_user(None)

            # Prevents from connecting to Shotgun.
            self._server_caps_mock = mock.patch(
                "tank_vendor.shotgun_api3.Shotgun.server_caps"
            )
            self._server_caps_mock.start()
            self.addCleanup(self._server_caps_mock.stop)

            # Avoids crash because we're not in a pipeline configuration.
            self._get_api_core_config_location_mock = mock.patch(
                "tank.util.shotgun.connection.__get_api_core_config_location",
                return_value="unused_path_location",
            )
            self._get_api_core_config_location_mock.start()
            self.addCleanup(self._get_api_core_config_location_mock.stop)

            # Mocks app store script user credentials retrieval
            self._get_app_store_key_from_shotgun_mock = mock.patch(
                "tank.descriptor.io_descriptor.appstore.IODescriptorAppStore."
                "_IODescriptorAppStore__get_app_store_key_from_shotgun",
                return_value=("abc", "123"),
            )
            self._get_app_store_key_from_shotgun_mock.start()
            self.addCleanup(self._get_app_store_key_from_shotgun_mock.stop)

        def tearDown(self):
            """
            Clear cached appstore connection
            """
            tank.util.shotgun.connection._g_sg_cached_connections = threading.local()
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
                expected_store_proxy=self._SITE_PROXY,
            )

        def test_connections_store_proxy(self):
            """
            When the app_store_http_proxy setting is set in shotgun.yml, the app
            store connections are expected to use the proxy setting.
            """
            self._run_test(
                site=self._SITE,
                source_proxy=self._SITE_PROXY,
                expected_store_proxy=self._SITE_PROXY,
            )

        def test_connections_both_proxy(self):
            """
            When both proxy settings are set, each connection has its own proxy.
            """
            self._run_test(
                site=self._SITE,
                source_proxy=self._SITE_PROXY,
                source_store_proxy=self._STORE_PROXY,
                expected_store_proxy=self._STORE_PROXY,
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
                expected_store_proxy=None,
            )

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
