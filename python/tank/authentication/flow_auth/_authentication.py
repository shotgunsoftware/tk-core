# Copyright (c) 2026 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.
"""
This module contains utilities for authenticating into Flow.
"""

from __future__ import annotations

import base64
import json
import time

from tank_vendor.adsk_auth import (
    AuthConfig,
)
from tank_vendor.adsk_auth import get_access_token as get_access_token_from_adsk_auth

from ... import LogManager
from ...util import LocalFileStorageManager
from ._constants import REQUIRED_SCOPES
from .errors import FlowAuthConfigurationError

logger = LogManager.get_logger(__name__)

_aps_configuration = None


def init_authentication(settings):
    """Initialize authentication configuration with configured settings.

    Args:
        settings: FlowAuthSettings (or duck-typed equivalent) containing
            auth_application_id, auth_base_url, auth_callback_url.

    Raises:
        FlowAuthConfigurationError: If required authentication settings are missing or invalid.
    """
    global _aps_configuration

    auth_application_id = settings.auth_application_id
    auth_base_url = settings.auth_base_url
    auth_callback_url = settings.auth_callback_url

    if not auth_application_id:
        raise FlowAuthConfigurationError(
            details="Required setting 'auth_application_id' is not configured."
        )
    if not auth_base_url:
        raise FlowAuthConfigurationError(
            details="Required setting 'auth_base_url' is not configured."
        )
    if not auth_callback_url:
        raise FlowAuthConfigurationError(
            details="Required setting 'auth_callback_url' is not configured."
        )

    _aps_configuration = AuthConfig(
        application_id=auth_application_id,
        base_url=auth_base_url,
        callback_url=auth_callback_url,
        description="Autodesk Toolkit",
        required_application_scopes=REQUIRED_SCOPES,
        storage_dir=LocalFileStorageManager.get_global_root(
            LocalFileStorageManager.CACHE
        ),
    )


def _get_aps_configuration():
    """Get the APS configuration.

    Returns:
        tank_vendor.adsk_auth.AuthConfig: The initialized auth configuration.

    Raises:
        RuntimeError: If authentication has not been initialized.
    """
    if _aps_configuration is None:
        raise RuntimeError(
            "Authentication not initialized. Call init_authentication() first."
        )
    return _aps_configuration


def check_token_expiry(token: str, buffer_seconds: int = 300) -> bool:
    """
    Check if the given token is expiring soon (within the buffer period).

    The Flow API can fail if the token is not yet expired but will expire soon,
    so we proactively refresh when within the buffer.

    Args:
        token: The access token to check.
        buffer_seconds: Seconds before expiry to consider the token "expiring soon".
            Defaults to 300 (5 minutes).

    Returns:
        True if the token is expiring soon or invalid, False if it has
        sufficient validity remaining.
    """
    try:
        payload = _decode_token_payload(token)
    except Exception as e:
        logger.error("Error decoding token: %s", e)
        return True

    exp_timestamp = payload.get("exp") if payload else None

    if not exp_timestamp:
        logger.warning(
            "Token does not contain 'exp' claim. Treating token as expiring soon."
        )
        return True

    current_timestamp = time.time()
    time_remaining = exp_timestamp - current_timestamp
    if time_remaining < buffer_seconds:
        logger.debug(
            "Token will expire in %.0f seconds, less than buffer of %s seconds.",
            time_remaining,
            buffer_seconds,
        )
        return True

    return False


def _decode_token_payload(token: str):
    """Decode JWT payload without verification (only used to read exp)."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        padding = (4 - len(payload_b64) % 4) % 4
        payload_b64 += "=" * padding
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes)
    except Exception:
        return None


def _auth_options_from_kwargs(kwargs):
    """Extract adsk_auth get_access_token options from kwargs (e.g. authentication_options)."""
    opts = kwargs.get("authentication_options")
    if opts is None:
        return {}
    return {
        "profile": getattr(opts, "user_profile", None),
        "force_refresh": getattr(opts, "force_refresh", False),
        "force_reauthentication": getattr(opts, "force_reauthentication", False),
        "time_out": getattr(opts, "time_out", 30.0),
        "browser": getattr(opts, "browser", None),
    }


def get_access_token(*args, **kwargs) -> str:
    """Get access token from file store or web (PKCE).

    Ensures the returned token has at least 5 minutes of validity remaining,
    since the Flow API can fail when the token is about to expire.
    """
    config = _get_aps_configuration()
    options = _auth_options_from_kwargs(kwargs)
    token = get_access_token_from_adsk_auth(config, **options)

    if check_token_expiry(token):
        logger.info("Access token is expiring within 5 minutes. Forcing a refresh.")
        options["force_refresh"] = True
        token = get_access_token_from_adsk_auth(config, **options)

    return token


def get_flow_access_token(**kwargs) -> str:
    """Get a Flow access token, lazy-initialising auth if needed.

    Safe to call without a prior ``init_authentication()`` — if bootstrap has
    not already initialised the APS configuration, settings are resolved from
    environment variables and initialisation is performed automatically.
    """
    if _aps_configuration is None:
        from ._settings import resolve_flow_auth_settings

        init_authentication(resolve_flow_auth_settings())
    return get_access_token(**kwargs)
