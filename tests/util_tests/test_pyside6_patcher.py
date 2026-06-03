# Copyright (c) 2023 Autodesk.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the ShotGrid Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the ShotGrid Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Autodesk.

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    TankTestBase,
    skip_if_pyside6,
)

from tank.util import pyside6_patcher


@skip_if_pyside6(found=False)
class PySide6PatcherTests(TankTestBase):
    """Tests PySide6 patcher functionality."""

    def test_patch(self):
        pass
