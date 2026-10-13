# Copyright (c) 2026 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""Errors for Flow / MEDM authentication."""

from ...errors import TankError


class FlowAuthError(TankError):
    """Base exception for Flow / MEDM authentication errors."""


class FlowAuthConfigurationError(FlowAuthError):
    """Raised when Flow auth settings are missing or invalid."""

    def __init__(self, details: str = ""):
        super().__init__(details)
        self.details = details
