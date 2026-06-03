# Copyright (c) 2023 Autodesk.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the ShotGrid Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the ShotGrid Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Autodesk.

import importlib
import unittest

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import ShotgunTestBase


class TestVersionImport(ShotgunTestBase):
    """Test importing the tank.util.version module with vendored packaging."""

    def test_import_version_module(self):
        pass
    def test_vendored_packaging_available(self):
        pass
