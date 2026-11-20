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
import tempfile
import time
import unittest
from unittest import mock

from tank_test.tank_test_base import setUpModule  # noqa
from tank_vendor.adsk_auth import file_store, token as adsk_token
from tank_vendor.adsk_auth.config import AuthConfig


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _make_jwt(payload):
    """Build an unsigned JWT-shaped string. The signature is never checked."""
    header = _b64(b'{"alg":"none"}')
    return f"{header}.{_b64(json.dumps(payload).encode('utf-8'))}.sig"


class IsTokenValidTests(unittest.TestCase):
    def test_expired_token_is_invalid(self):
        token = _make_jwt({"exp": int(time.time()) - 60})
        self.assertFalse(adsk_token._is_token_valid(token))

    def test_float_exp_is_accepted(self):
        token = _make_jwt({"exp": time.time() + 3600.5})
        self.assertTrue(adsk_token._is_token_valid(token))

    def test_future_token_is_valid(self):
        token = _make_jwt({"exp": int(time.time()) + 3600})
        self.assertTrue(adsk_token._is_token_valid(token))

    def test_invalid_base64_is_invalid(self):
        self.assertFalse(adsk_token._is_token_valid("header.@@@.sig"))

    def test_invalid_exp_is_invalid(self):
        for exp in ("soon", None, [], float("inf")):
            with self.subTest(exp=exp):
                token = _make_jwt({"exp": exp})
                self.assertFalse(adsk_token._is_token_valid(token))

    def test_missing_exp_is_valid(self):
        self.assertTrue(adsk_token._is_token_valid(_make_jwt({"sub": "alice"})))

    def test_non_json_payload_is_invalid(self):
        token = f"{_b64(b'{}')}.{_b64(b'not json')}.sig"
        self.assertFalse(adsk_token._is_token_valid(token))

    def test_non_object_payload_is_invalid(self):
        token = f"{_b64(b'{}')}.{_b64(b'[1, 2]')}.sig"
        self.assertFalse(adsk_token._is_token_valid(token))

    def test_wrong_segment_count_is_invalid(self):
        for value in ("", "abc", "a.b", "a.b.c.d"):
            with self.subTest(value=value):
                self.assertFalse(adsk_token._is_token_valid(value))


class GetAccessTokenTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.config = AuthConfig(
            application_id="myapp",
            base_url="https://example.com",
            callback_url="http://localhost:1234",
            required_application_scopes=["data:read"],
            storage_dir=self._tmpdir.name,
        )
        adsk_token._access_token_cache.clear()

        patcher = mock.patch.object(
            adsk_token,
            "exchange_refresh_token",
            return_value={"access_token": "refreshed", "refresh_token": "ref2"},
        )
        self.mock_refresh = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(
            adsk_token,
            "web_authenticate",
            return_value={"access_token": "from_browser"},
        )
        self.mock_browser = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        adsk_token._access_token_cache.clear()
        self._tmpdir.cleanup()

    def _store(self, tokens):
        file_store.persist_tokens(self._tmpdir.name, "myapp", "alice", tokens)

    def test_expired_cached_token_falls_back_to_store(self):
        stored = _make_jwt({"exp": int(time.time()) + 3600})
        self._store({"access_token": stored})
        adsk_token._access_token_cache["alice"] = _make_jwt(
            {"exp": int(time.time()) - 60}
        )
        self.assertEqual(
            adsk_token.get_access_token(self.config, profile="alice"), stored
        )

    def test_expired_stored_token_is_refreshed(self):
        self._store(
            {
                "access_token": _make_jwt({"exp": int(time.time()) - 60}),
                "refresh_token": "ref1",
            }
        )
        self.assertEqual(
            adsk_token.get_access_token(self.config, profile="alice"), "refreshed"
        )
        self.mock_refresh.assert_called_once_with(self.config, "ref1")
        self.mock_browser.assert_not_called()

    def test_malformed_stored_token_without_refresh_uses_browser(self):
        self._store({"access_token": "not-a-jwt"})
        self.assertEqual(
            adsk_token.get_access_token(self.config, profile="alice"), "from_browser"
        )
        self.mock_refresh.assert_not_called()

    def test_valid_cached_token_is_returned(self):
        cached = _make_jwt({"exp": int(time.time()) + 3600})
        adsk_token._access_token_cache["alice"] = cached
        self.assertEqual(
            adsk_token.get_access_token(self.config, profile="alice"), cached
        )
        self.mock_refresh.assert_not_called()
        self.mock_browser.assert_not_called()

    def test_valid_stored_token_is_returned_and_cached(self):
        stored = _make_jwt({"exp": int(time.time()) + 3600})
        self._store({"access_token": stored})
        self.assertEqual(
            adsk_token.get_access_token(self.config, profile="alice"), stored
        )
        self.assertEqual(adsk_token._access_token_cache["alice"], stored)
        self.mock_refresh.assert_not_called()
        self.mock_browser.assert_not_called()
