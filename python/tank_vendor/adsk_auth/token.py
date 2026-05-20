# Copyright (c) 2025 Shotgun Software Inc.
# CONFIDENTIAL AND PROPRIETARY

"""Get access token: keyring -> refresh -> browser PKCE."""

from __future__ import annotations

import logging
from typing import Any, Optional

import jwt
from urllib.error import HTTPError

from .config import AuthConfig
from .keyring_store import (
    delete_tokens,
    get_access_token as get_access_token_from_keyring,
    get_refresh_token,
    get_user_profile,
    persist_tokens,
)
from .pkce import exchange_refresh_token, web_authenticate

_logger = logging.getLogger(__name__)

# In-memory cache: profile -> access_token (avoids keyring read every call)
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
    Return a valid access token: use cache, then keyring, then refresh, then browser PKCE.

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
        try:
            jwt.decode(cached, options={"verify_signature": False, "verify_exp": True})
            return cached
        except (jwt.ExpiredSignatureError, jwt.DecodeError):
            pass

    if force_reauthentication:
        delete_tokens(config.application_id, user_profile)

    # 2. Valid token in keyring?
    if not (force_reauthentication or force_refresh):
        try:
            access_token = get_access_token_from_keyring(
                config.application_id, user_profile
            )
            if access_token:
                jwt.decode(
                    access_token,
                    options={"verify_signature": False, "verify_exp": True},
                )
                _access_token_cache[user_profile] = access_token
                return access_token
        except (jwt.ExpiredSignatureError, jwt.DecodeError):
            pass

    # 3. Refresh token?
    try:
        refresh_token = get_refresh_token(config.application_id, user_profile)
        if refresh_token:
            _logger.debug("Using refresh token")
            token_dict = exchange_refresh_token(config, refresh_token)
            persist_tokens(config.application_id, user_profile, token_dict)
            access_token = token_dict["access_token"]
            _access_token_cache[user_profile] = access_token
            return access_token
    except (RuntimeError, HTTPError) as e:
        _logger.debug("Refresh failed: %s", e)

    # 4. Browser PKCE
    _logger.warning("Opening browser to authenticate (timeout %.1fs)", time_out)
    token_dict = web_authenticate(config, time_out=time_out, browser=browser)
    persist_tokens(config.application_id, user_profile, token_dict)
    access_token = token_dict["access_token"]
    _access_token_cache[user_profile] = access_token
    return access_token


def clear_stored_tokens(config: AuthConfig, profile: Optional[str] = None) -> None:
    """Remove tokens from keyring and in-memory cache for this app/profile."""
    user_profile = get_user_profile(profile)
    _access_token_cache.pop(user_profile, None)
    delete_tokens(config.application_id, user_profile)
