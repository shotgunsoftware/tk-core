# Copyright (c) 2026 Autodesk.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the ShotGrid Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the ShotGrid Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Autodesk.
"""Case where we check defining a Python dataclass won't fail during hook loading.

The dataclasses module checks the `.sys.modules` for the ``Data`` class's ``__module__``
during type checking, so it should exist in there and not fatally error when loading
this hook.

This is a regression test for https://github.com/shotgunsoftware/tk-core/pull/1047
(https://github.com/shotgunsoftware/tk-core/commit/eaaadceafa4b449f819cf9c1b05cba229daaeeab)
"""

from __future__ import annotations

from dataclasses import dataclass

import sgtk


@dataclass(frozen=True)
class Data:
    name: str | None
    number: int | float
    error: (
        sgtk.authentication.AuthenticationError
        | sgtk.authentication.IncompleteCredentials
        | sgtk.authentication.AuthenticationCancelled
        | sgtk.authentication.ConsoleLoginNotSupportedError
        | None
    ) = None


class TestHook(sgtk.get_hook_baseclass()):
    def execute(self):
        return Data("foo", 123)

    def second_method(self):
        return Data(
            None,
            -3.1419,
            error=sgtk.authentication.AuthenticationCancelled(),
        )
