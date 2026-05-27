# Copyright (c) 2026 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import base64
import json
import time

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import mock, ShotgunTestBase

from tank.authentication import flow_auth
from tank.authentication.flow_auth import _authentication as flow_auth_impl
from tank.authentication.flow_auth.errors import FlowAuthConfigurationError


def _make_jwt(payload):
    """Build a minimal unsigned JWT-shaped string. Header/signature are ignored
    by the unverified decode used in flow_auth."""
    header_b64 = (
        base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode("ascii")
    )
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8"))
        .rstrip(b"=")
        .decode("ascii")
    )
    return f"{header_b64}.{payload_b64}.sig"


class _Settings:
    """Duck-typed FlowAuthSettings stand-in."""

    def __init__(
        self,
        app_id="app",
        base_url="https://aps.example.com",
        callback="http://localhost:8080/cb",
    ):
        self.auth_application_id = app_id
        self.auth_base_url = base_url
        self.auth_callback_url = callback


class InitAuthenticationTests(ShotgunTestBase):
    def setUp(self):
        super().setUp()
        flow_auth_impl._aps_configuration = None

    def tearDown(self):
        flow_auth_impl._aps_configuration = None
        super().tearDown()

    def test_missing_application_id_raises(self):
        with self.assertRaises(FlowAuthConfigurationError):
            flow_auth.init_authentication(_Settings(app_id=""))

    def test_missing_base_url_raises(self):
        with self.assertRaises(FlowAuthConfigurationError):
            flow_auth.init_authentication(_Settings(base_url=""))

    def test_missing_callback_url_raises(self):
        with self.assertRaises(FlowAuthConfigurationError):
            flow_auth.init_authentication(_Settings(callback=""))

    def test_valid_settings_initializes_config(self):
        flow_auth.init_authentication(_Settings())
        self.assertIsNotNone(flow_auth_impl._aps_configuration)
        self.assertEqual(flow_auth_impl._aps_configuration.application_id, "app")


class CheckTokenExpiryTests(ShotgunTestBase):
    def test_fresh_token_returns_false(self):
        token = _make_jwt({"exp": int(time.time()) + 3600})  # 1h in future
        self.assertFalse(flow_auth.check_token_expiry(token))

    def test_expiring_within_buffer_returns_true(self):
        token = _make_jwt({"exp": int(time.time()) + 60})  # well under 300s buffer
        self.assertTrue(flow_auth.check_token_expiry(token))

    def test_expired_token_returns_true(self):
        token = _make_jwt({"exp": int(time.time()) - 60})
        self.assertTrue(flow_auth.check_token_expiry(token))

    def test_token_without_exp_claim_returns_true(self):
        token = _make_jwt({"sub": "user"})
        self.assertTrue(flow_auth.check_token_expiry(token))

    def test_custom_buffer(self):
        token = _make_jwt({"exp": int(time.time()) + 400})
        self.assertFalse(flow_auth.check_token_expiry(token, buffer_seconds=300))
        self.assertTrue(flow_auth.check_token_expiry(token, buffer_seconds=600))


class DecodeTokenPayloadTests(ShotgunTestBase):
    def test_valid_jwt_returns_payload(self):
        payload = {"sub": "alice", "exp": 1234567890}
        token = _make_jwt(payload)
        self.assertEqual(flow_auth_impl._decode_token_payload(token), payload)

    def test_malformed_jwt_returns_none(self):
        self.assertIsNone(
            flow_auth_impl._decode_token_payload("not.a.jwt.too.many.dots")
        )

    def test_non_jwt_string_returns_none(self):
        self.assertIsNone(flow_auth_impl._decode_token_payload("plain-string"))

    def test_invalid_base64_returns_none(self):
        self.assertIsNone(flow_auth_impl._decode_token_payload("a.@@@.c"))


class GetFlowAccessTokenTests(ShotgunTestBase):
    def setUp(self):
        super().setUp()
        flow_auth_impl._aps_configuration = None

    def tearDown(self):
        flow_auth_impl._aps_configuration = None
        super().tearDown()

    @mock.patch(
        "tank.authentication.flow_auth._authentication.get_access_token_from_adsk_auth"
    )
    def test_delegates_when_already_initialised(self, mock_adsk):
        flow_auth.init_authentication(_Settings())
        fresh = _make_jwt({"exp": int(time.time()) + 3600})
        mock_adsk.return_value = fresh

        result = flow_auth.get_flow_access_token()

        self.assertEqual(result, fresh)
        self.assertEqual(mock_adsk.call_count, 1)

    @mock.patch(
        "tank.authentication.flow_auth._authentication.get_access_token_from_adsk_auth"
    )
    @mock.patch(
        "tank.authentication.flow_auth._settings.resolve_flow_auth_settings",
        return_value=_Settings(),
    )
    def test_lazy_init_when_not_initialised(self, mock_resolve, mock_adsk):
        fresh = _make_jwt({"exp": int(time.time()) + 3600})
        mock_adsk.return_value = fresh

        result = flow_auth.get_flow_access_token()

        # resolve_flow_auth_settings() was called to build settings, and
        # _aps_configuration is now populated (real init_authentication ran).
        mock_resolve.assert_called_once()
        self.assertIsNotNone(flow_auth_impl._aps_configuration)
        self.assertEqual(result, fresh)


class FlowAuthenticationHandlerTests(ShotgunTestBase):
    def setUp(self):
        super().setUp()
        flow_auth_impl._aps_configuration = None

    def tearDown(self):
        flow_auth_impl._aps_configuration = None
        super().tearDown()

    @mock.patch(
        "tank.authentication.flow_auth._authentication.get_access_token_from_adsk_auth"
    )
    def test_get_authentication_token_returns_token(self, mock_adsk):
        flow_auth.init_authentication(_Settings())
        fresh = _make_jwt({"exp": int(time.time()) + 3600})
        mock_adsk.return_value = fresh

        from tank.authentication.flow_auth import FlowAuthenticationHandler

        handler = FlowAuthenticationHandler()
        self.assertEqual(handler.get_authentication_token(), fresh)


class GetFlowClientTests(ShotgunTestBase):
    _DEFAULT = "https://default.example.com/graphql"

    def setUp(self):
        super().setUp()
        flow_auth_impl._aps_configuration = None
        # Stub the GQL SDK vendor modules so tests run without the zip installed.
        self._mock_gql_cls = mock.MagicMock()
        config_mod = mock.MagicMock(DEFAULT_ENDPOINT=self._DEFAULT)
        data_mod = mock.MagicMock(GQLClient=self._mock_gql_cls)
        self._sys_modules_patch = mock.patch.dict(
            "sys.modules",
            {
                "tank_vendor.adsk.flow.data": data_mod,
                "tank_vendor.adsk.flow.data.config": config_mod,
            },
        )
        self._sys_modules_patch.start()

    def tearDown(self):
        self._sys_modules_patch.stop()
        flow_auth_impl._aps_configuration = None
        super().tearDown()

    @mock.patch(
        "tank.authentication.flow_auth._authentication.get_access_token_from_adsk_auth"
    )
    def test_returns_client_with_default_endpoint(self, mock_adsk):
        flow_auth.init_authentication(_Settings())
        mock_adsk.return_value = _make_jwt({"exp": int(time.time()) + 3600})

        flow_auth.get_flow_client()

        self._mock_gql_cls.assert_called_once()
        _, kwargs = self._mock_gql_cls.call_args
        self.assertEqual(kwargs["endpoint"], self._DEFAULT)
        self.assertIn("auth_handler", kwargs)

    @mock.patch(
        "tank.authentication.flow_auth._authentication.get_access_token_from_adsk_auth"
    )
    def test_passes_custom_endpoint(self, mock_adsk):
        flow_auth.init_authentication(_Settings())
        mock_adsk.return_value = _make_jwt({"exp": int(time.time()) + 3600})
        custom_url = "https://staging.example.com/graphql"

        flow_auth.get_flow_client(custom_url)

        _, kwargs = self._mock_gql_cls.call_args
        self.assertEqual(kwargs["endpoint"], custom_url)


class GetAccessTokenTests(ShotgunTestBase):
    def setUp(self):
        super().setUp()
        flow_auth.init_authentication(_Settings())

    def tearDown(self):
        flow_auth_impl._aps_configuration = None
        super().tearDown()

    @mock.patch(
        "tank.authentication.flow_auth._authentication.get_access_token_from_adsk_auth"
    )
    def test_returns_fresh_token_without_refresh(self, mock_adsk):
        fresh = _make_jwt({"exp": int(time.time()) + 3600})
        mock_adsk.return_value = fresh

        result = flow_auth.get_access_token()

        self.assertEqual(result, fresh)
        self.assertEqual(mock_adsk.call_count, 1)

    @mock.patch(
        "tank.authentication.flow_auth._authentication.get_access_token_from_adsk_auth"
    )
    def test_forces_refresh_when_expiring_soon(self, mock_adsk):
        # First call returns a token expiring within the buffer; second call
        # returns a fresh one after force_refresh is set.
        expiring = _make_jwt({"exp": int(time.time()) + 60})
        fresh = _make_jwt({"exp": int(time.time()) + 3600})
        mock_adsk.side_effect = [expiring, fresh]

        result = flow_auth.get_access_token()

        self.assertEqual(result, fresh)
        self.assertEqual(mock_adsk.call_count, 2)
        # The second invocation should have force_refresh=True.
        _, second_call_kwargs = mock_adsk.call_args_list[1]
        self.assertTrue(second_call_kwargs.get("force_refresh"))

    def test_get_access_token_without_init_raises(self):
        flow_auth_impl._aps_configuration = None
        with self.assertRaises(RuntimeError):
            flow_auth.get_access_token()
