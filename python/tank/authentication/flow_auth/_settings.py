# Copyright (c) 2026 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""Settings resolver for Flow / MEDM authentication."""

from __future__ import annotations

import os
from dataclasses import dataclass

from ._constants import (
    DEFAULT_AUTH_APPLICATION_ID,
    DEFAULT_AUTH_BASE_URL,
    DEFAULT_AUTH_CALLBACK_URL,
)


@dataclass
class FlowAuthSettings:
    """APS credentials required to perform PKCE authentication."""

    auth_application_id: str
    auth_base_url: str
    auth_callback_url: str


def resolve_flow_auth_settings() -> FlowAuthSettings:
    """
    Resolve APS auth settings: env-var overrides, falling back to hardcoded defaults.

    Override env vars:
        TK_FLOW_AUTH_APPLICATION_ID
        TK_FLOW_AUTH_BASE_URL
        TK_FLOW_AUTH_CALLBACK_URL
    """
    return FlowAuthSettings(
        auth_application_id=os.environ.get(
            "TK_FLOW_AUTH_APPLICATION_ID", DEFAULT_AUTH_APPLICATION_ID
        ),
        auth_base_url=os.environ.get("TK_FLOW_AUTH_BASE_URL", DEFAULT_AUTH_BASE_URL),
        auth_callback_url=os.environ.get(
            "TK_FLOW_AUTH_CALLBACK_URL", DEFAULT_AUTH_CALLBACK_URL
        ),
    )