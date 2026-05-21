# Copyright (c) 2026 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""Constants for Flow / MEDM authentication."""

AM_READY_PROJECT_FIELD = "sg_flow_am_id"

# TODO(SG-43166): confirm production APS values with Julien.
DEFAULT_AUTH_APPLICATION_ID = "<TBD>"
DEFAULT_AUTH_BASE_URL = "https://developer.api.autodesk.com"
DEFAULT_AUTH_CALLBACK_URL = "http://localhost:8080/api/auth/callback"

# Previously "openid" was also requested but is not used or required for
# authentication to Flow, and exceeded Windows Credential Manager's 1280-char
# limit. Safe to exclude.
REQUIRED_SCOPES = [
    "data:read",
    "data:write",
    "data:create",
]
