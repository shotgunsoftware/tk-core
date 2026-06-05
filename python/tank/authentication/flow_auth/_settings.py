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

from ...flowam.constants import (
    FLOW_AUTH_APP_ID,
    FLOW_AUTH_BASE_URL,
    FLOW_AUTH_CALLBACK_URL,
)

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


def resolve_flow_auth_settings(
    overrides: dict[str, str] | None = None,
) -> FlowAuthSettings:
    """
    Resolve APS auth settings: env-var overrides, falling back to hardcoded defaults.

    Args:
        overrides: Dictionary which can contain the following override keys:
                    FLOW_AUTH_APP_ID
                    FLOW_AUTH_BASE_URL
                    FLOW_AUTH_CALLBACK_URL
    """
    overrides = {} if overrides is None else overrides
    return FlowAuthSettings(
        auth_application_id=overrides.get(
            FLOW_AUTH_APP_ID, DEFAULT_AUTH_APPLICATION_ID
        ),
        auth_base_url=overrides.get(FLOW_AUTH_BASE_URL, DEFAULT_AUTH_BASE_URL),
        auth_callback_url=overrides.get(FLOW_AUTH_CALLBACK_URL, DEFAULT_AUTH_CALLBACK_URL),
    )
