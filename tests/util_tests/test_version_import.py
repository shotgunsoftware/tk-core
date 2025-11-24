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
        """Test that tank.util.version can be imported successfully."""

        # This should not raise any ImportError
        from tank.util import version

        # Reload to ensure clean import
        importlib.reload(version)

        # Verify core functions are available
        self.assertTrue(hasattr(version, "is_version_newer"))
        self.assertTrue(hasattr(version, "is_version_older"))
        self.assertTrue(hasattr(version, "normalize_version_format"))

    def test_vendored_packaging_available(self):
        """Test that vendored packaging is available and functional."""

        # Should be able to import vendored packaging
        from tank_vendor.packaging.version import parse

        # Basic smoke test - should not raise any exception
        version_obj = parse("1.0.0")
        self.assertEqual(str(version_obj), "1.0.0")
