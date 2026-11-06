# Copyright (c) 2025 Shotgun Software Inc.
# CONFIDENTIAL AND PROPRIETARY

"""APS PKCE configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class AuthConfig:
    """Configuration for APS PKCE authentication."""

    application_id: str
    base_url: str
    callback_url: str
    required_application_scopes: List[str]
    storage_dir: str
    description: str = ""

    def __post_init__(self) -> None:
        if not self.application_id or not self.application_id.strip():
            raise ValueError("application_id is required")
        if not self.base_url or not self.base_url.strip():
            raise ValueError("base_url is required")
        if not self.callback_url or not self.callback_url.strip():
            raise ValueError("callback_url is required")
        if not self.required_application_scopes:
            raise ValueError("required_application_scopes must not be empty")
        if not self.storage_dir or not self.storage_dir.strip():
            raise ValueError("storage_dir is required")
        self.base_url = _normalize_base_url(self.base_url.strip())
        self.application_id = self.application_id.strip()
        self.callback_url = self.callback_url.strip()


def _normalize_base_url(base_url: str) -> str:
    """Normalize base URL for APS (scheme + netloc)."""
    from urllib.parse import urlsplit

    scheme, netloc, path, _, _ = urlsplit(base_url)
    if scheme == "" and netloc == "" and path:
        if path.startswith("localhost") or path.startswith("localhost/"):
            port = path.split("/")[0].split(":")[-1] if ":" in path else ""
            return f"http://localhost:{port}" if port else "http://localhost"
        first = path.split("/")[0]
        return f"https://{first}"
    if scheme in ("http", "https"):
        return f"{scheme}://{netloc}"
    raise ValueError(f"base_url must use http or https, got scheme={scheme!r}")
