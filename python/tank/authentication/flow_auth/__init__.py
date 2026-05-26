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
Flow / MEDM authentication for Toolkit bootstrap.

Triggered during bootstrap when a project is "AM-ready". Obtains an APS
access token via PKCE; the token is cached in a local file store for reuse.
"""

from ._authentication import (
    init_authentication,
    get_access_token,
    check_token_expiry,
)
from ._constants import AM_READY_PROJECT_FIELD
from ._settings import FlowAuthSettings, resolve_flow_auth_settings
from .errors import FlowAuthError, FlowAuthConfigurationError

__all__ = [
    "init_authentication",
    "get_access_token",
    "check_token_expiry",
    "FlowAuthSettings",
    "resolve_flow_auth_settings",
    "FlowAuthError",
    "FlowAuthConfigurationError",
    "AM_READY_PROJECT_FIELD",
]
