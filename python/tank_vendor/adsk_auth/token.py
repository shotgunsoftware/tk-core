# Copyright (c) 2025 Shotgun Software Inc.
# CONFIDENTIAL AND PROPRIETARY

"""Get access token: file store -> refresh -> browser PKCE."""

from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any, Optional
from urllib.error import HTTPError

from .config import AuthConfig
from .file_store import delete_tokens
from .file_store import get_access_token as get_access_token_from_store
from .file_store import get_refresh_token, get_user_profile, persist_tokens
from .pkce import exchange_refresh_token, web_authenticate

_logger = logging.getLogger(__name__)

# In-memory cache: profile -> access_token (avoids file read every call)
_access_token_cache: dict[str, str] = {}


def get_access_token(
    config: AuthConfig,
    *,
    profile: Optional[str] = None,
    force_refresh: bool = False,
    force_reauthentication: bool = False,
    time_out: float = 30.0,
    browser: Any = None,
) -> str:
    """
    Return a valid access token: use cache, then file store, then refresh, then browser PKCE.

    Raises:
        RuntimeError: If a token could not be obtained.
    """
    global _access_token_cache
    user_profile = get_user_profile(profile)

    if force_reauthentication or force_refresh:
        _access_token_cache.pop(user_profile, None)

    # 1. Valid token in cache?
    cached = _access_token_cache.get(user_profile)
    if cached and not (force_refresh or force_reauthentication):
        if _is_token_valid(cached):
            return cached

    if force_reauthentication:
        delete_tokens(config.storage_dir, config.application_id, user_profile)

    # 2. Valid token in file store?
    if not (force_reauthentication or force_refresh):
        access_token = get_access_token_from_store(
            config.storage_dir, config.application_id, user_profile
        )
        if access_token and _is_token_valid(access_token):
            _access_token_cache[user_profile] = access_token
            return access_token

    # 3. Refresh token?
    try:
        refresh_token = get_refresh_token(
            config.storage_dir, config.application_id, user_profile
        )
        if refresh_token:
            _logger.debug("Using refresh token")
            token_dict = exchange_refresh_token(config, refresh_token)
            persist_tokens(config.storage_dir, config.application_id, user_profile, token_dict)
            access_token = token_dict["access_token"]
            _access_token_cache[user_profile] = access_token
            return access_token
    except (RuntimeError, HTTPError) as e:
        _logger.debug("Refresh failed: %s", e)

    # 4. Browser PKCE
    _logger.warning("Opening browser to authenticate (timeout %.1fs)", time_out)
    token_dict = web_authenticate(config, time_out=time_out, browser=browser)
    persist_tokens(config.storage_dir, config.application_id, user_profile, token_dict)
    access_token = token_dict["access_token"]
    _access_token_cache[user_profile] = access_token
    return access_token


def clear_stored_tokens(config: AuthConfig, profile: Optional[str] = None) -> None:
    """Remove tokens from file store and in-memory cache for this app/profile."""
    user_profile = get_user_profile(profile)
    _access_token_cache.pop(user_profile, None)
    delete_tokens(config.storage_dir, config.application_id, user_profile)


def _is_token_valid(token: str) -> bool:
    """
    Check that an access token is a well-formed JWT that has not expired.

    Only the "exp" claim is read: the signature is not verified, since the server
    does that. This deliberately avoids PyJWT, which imports any cryptography
    package found on sys.path. In FPT Desktop, that could load an incompatible
    cryptography before tk-framework-desktopserver loads its own bundled copy.

    A token without an "exp" claim is considered valid.
    """
    parts = token.split(".")
    if len(parts) != 3:
        return False

    # JWT segments are base64url encoded without padding.
    payload_segment = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_segment))
    except ValueError:
        return False

    if not isinstance(payload, dict):
        return False

    if "exp" not in payload:
        return True

    try:
        return int(payload["exp"]) > time.time()
    except (OverflowError, TypeError, ValueError):
        return False
