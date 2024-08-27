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

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
)


class TestVersionImport(ShotgunTestBase):
    """Test importing the tank.util.version module."""

    def test_import_version(self):
        """Test importing the tank.util.version module."""

        # Import the version module
        from tank.util import version
        # Reload the module in case it was already imported
        importlib.reload(version)
        # Sanity check the setuptools was imported successfully
        assert version.LooseVersion

    def test_import_version_missing_setuptools_distutils(self):
        """Test importing the tank.util.version module when setuptools is missing _distutils."""

        # Mock the sys.modules so that the import for setuptools._distutils.vesrion raises a
        # ModuleNotFound exception (to mock python environments where this module may not be
        # available)
        with mock.patch.dict('sys.modules', {"setuptools._distutils.version": None}):
            # Import the version module
            from tank.util import version
            # Reload the module in case it was already imported
            importlib.reload(version)
            # Sanity check the setuptools was imported successfully
            assert version.LooseVersion
