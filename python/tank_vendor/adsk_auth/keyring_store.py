# Copyright (c) 2025 Shotgun Software Inc.
# CONFIDENTIAL AND PROPRIETARY

"""Token storage via the keyring library (OS credential store)."""

from __future__ import annotations

import getpass
import logging
from typing import Any, Dict

import keyring

_logger = logging.getLogger(__name__)

SERVICE_PREFIX = "adsk.flow"
TOKEN_TYPES = ("access_token", "refresh_token")


def _service_name(application_id: str, token_type: str) -> str:
    return f"{SERVICE_PREFIX}.{application_id}.{token_type}"


def get_access_token(application_id: str, profile: str) -> str | None:
    """Read access token from keyring."""
    return keyring.get_password(
        _service_name(application_id, "access_token"),
        profile,
    )


def get_refresh_token(application_id: str, profile: str) -> str | None:
    """Read refresh token from keyring."""
    return keyring.get_password(
        _service_name(application_id, "refresh_token"),
        profile,
    )


def persist_tokens(
    application_id: str,
    profile: str,
    tokens: Dict[str, Any],
) -> None:
    """Store token dict (access_token, refresh_token) in keyring."""
    for token_type in TOKEN_TYPES:
        if token_type in tokens and tokens[token_type]:
            keyring.set_password(
                _service_name(application_id, token_type),
                profile,
                tokens[token_type],
            )


def delete_tokens(application_id: str, profile: str) -> None:
    """Remove all stored tokens for this app and profile."""
    for token_type in TOKEN_TYPES:
        try:
            keyring.delete_password(
                _service_name(application_id, token_type),
                profile,
            )
        except keyring.errors.PasswordDeleteError:
            _logger.debug(
                "No keyring entry for %s/%s/%s",
                application_id,
                token_type,
                profile,
            )


def get_user_profile(profile: str | None) -> str:
    """Return profile (username) for keyring; default current OS user."""
    return profile or getpass.getuser()
