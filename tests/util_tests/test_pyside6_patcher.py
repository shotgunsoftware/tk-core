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
        """Test the PySide6Patcher patch method that patches PySide6 as PySide."""

        core, gui, _ = pyside6_patcher.PySide6Patcher.patch()
        # Assert the core ang gui modules are created and returned
        assert core
        assert gui
        # Assert QtCore attributes
        assert core.Qt.MidButton == core.Qt.MiddleButton
        assert core.QRegExp == core.QRegularExpression
        # Assert QtGui attributes
        assert gui.QApplication.desktop
        assert gui.QAbstractButton.animateClick
        assert gui.QSortFilterProxyModel.filterRegExp == gui.QSortFilterProxyModel.filterRegularExpression
        assert gui.QSortFilterProxyModel.setFilterRegExp == gui.QSortFilterProxyModel.setFilterRegularExpression
        assert gui.QDesktopWidget == gui.QScreen
        assert gui.QFontMetrics.width == gui.QFontMetrics.horizontalAdvance
        assert gui.QFont.setWeight == gui.QFont.setLegacyWeight
        assert gui.QHeaderView.setResizeMode == gui.QHeaderView.setSectionResizeMode
        assert gui.QPainter.HighQualityAntialiasing == gui.QPainter.Antialiasing
        assert gui.QPalette.Background == gui.QPalette.Window
