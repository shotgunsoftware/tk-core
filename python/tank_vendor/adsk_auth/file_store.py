# Copyright (c) 2025 Shotgun Software Inc.
# CONFIDENTIAL AND PROPRIETARY

"""Token storage via a local JSON file (replaces keyring dependency)."""

from __future__ import annotations

import getpass
import json
import logging
import os
import sys
from typing import Any, Dict

_logger = logging.getLogger(__name__)

SERVICE_PREFIX = "adsk.flow"
TOKEN_TYPES = ("access_token", "refresh_token")

_TOKEN_FILE_NAME = "adsk_flow_tokens.json"


def _service_name(application_id: str, token_type: str) -> str:
    return f"{SERVICE_PREFIX}.{application_id}.{token_type}"


def _token_file_path(storage_dir: str) -> str:
    return os.path.join(storage_dir, _TOKEN_FILE_NAME)


def _load(storage_dir: str) -> Dict[str, Any]:
    path = _token_file_path(storage_dir)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        _logger.debug("Could not read token file %s", path, exc_info=True)
        return {}


def _save(storage_dir: str, data: Dict[str, Any]) -> None:
    if not os.path.exists(storage_dir):
        old_umask = os.umask(0o077)
        try:
            os.makedirs(storage_dir, 0o700)
        finally:
            os.umask(old_umask)

    path = _token_file_path(storage_dir)
    old_umask = os.umask(0o177)
    try:
        with open(path, "w") as fh:
            json.dump(data, fh)
    finally:
        os.umask(old_umask)

    # Belt-and-suspenders: explicitly set permissions on POSIX.
    if sys.platform != "win32":
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def get_access_token(
    storage_dir: str, application_id: str, profile: str
) -> str | None:
    """Read access token from the file store."""
    data = _load(storage_dir)
    return data.get(_service_name(application_id, "access_token"), {}).get(profile)


def get_refresh_token(
    storage_dir: str, application_id: str, profile: str
) -> str | None:
    """Read refresh token from the file store."""
    data = _load(storage_dir)
    return data.get(_service_name(application_id, "refresh_token"), {}).get(profile)


def persist_tokens(
    storage_dir: str,
    application_id: str,
    profile: str,
    tokens: Dict[str, Any],
) -> None:
    """Store token dict (access_token, refresh_token) in the file store."""
    data = _load(storage_dir)
    for token_type in TOKEN_TYPES:
        if tokens.get(token_type):
            service = _service_name(application_id, token_type)
            data.setdefault(service, {})[profile] = tokens[token_type]
    _save(storage_dir, data)


def delete_tokens(storage_dir: str, application_id: str, profile: str) -> None:
    """Remove all stored tokens for this app and profile."""
    data = _load(storage_dir)
    changed = False
    for token_type in TOKEN_TYPES:
        service = _service_name(application_id, token_type)
        if service in data and profile in data[service]:
            del data[service][profile]
            changed = True
    if changed:
        _save(storage_dir, data)


def get_user_profile(profile: str | None) -> str:
    """Return profile (username) for the store; default current OS user."""
    return profile or getpass.getuser()
