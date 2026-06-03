# Copyright (c) 2023 Autodesk.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the ShotGrid Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the ShotGrid Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Autodesk.

import types
import unittest.mock

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    TankTestBase,
    skip_if_pyside2,
    skip_if_pyside6,
)
from tank.util import qt_importer


class QtImporterTests(TankTestBase):
    """Tests QtImporter functionality."""

    @skip_if_pyside2(found=False)
    def test_qt_importer_with_pyside2_interface_qt4(self):
        pass
    @skip_if_pyside2(found=False)
    def test_qt_importer_with_pyside2_interface_qt5(self):
        pass
    @skip_if_pyside6(found=False)
    @skip_if_pyside2(found=True)
    def test_qt_importer_with_pyside6_interface_qt4(self):
        pass
    @skip_if_pyside6(found=False)
    @skip_if_pyside2(found=True)
    def test_qt_importer_with_pyside6_interface_qt6(self):
        pass
    @skip_if_pyside2(found=False)
    @skip_if_pyside6(found=True)
    @unittest.mock.patch(
        # Ensure the QtWebEngineWidgets module is present
        "PySide2.QtWebEngineWidgets"
    )
    @unittest.mock.patch.dict(
        # Set the SHOTGUN_SKIP_QTWEBENGINEWIDGETS_IMPORT variable
        "os.environ",
        {"SHOTGUN_SKIP_QTWEBENGINEWIDGETS_IMPORT": "1"}
    )
    def test_skip_webengine_qt5(self, *mocks):
        pass
    @skip_if_pyside6(found=False)
    @skip_if_pyside2(found=True)
    @unittest.mock.patch(
        # Ensure the QtWebEngineWidgets module is present
        "PySide6.QtWebEngineWidgets"
    )
    @unittest.mock.patch.dict(
        # Set the SHOTGUN_SKIP_QTWEBENGINEWIDGETS_IMPORT variable
        "os.environ",
        {"SHOTGUN_SKIP_QTWEBENGINEWIDGETS_IMPORT": "1"}
    )
    def test_skip_webengine_qt6(self, *mocks):
        pass
