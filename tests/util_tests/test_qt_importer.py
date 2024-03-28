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
    skip_if_pyside,
    skip_if_pyside2,
    skip_if_pyside6,
    skip_if_pyqt4,
)
from tank.util import qt_importer


class QtImporterTests(TankTestBase):
    """Tests QtImporter functionality."""

    @skip_if_pyside2(found=False)
    def test_qt_importer_with_pyside2_interface_qt4(self):
        """
        Test the QtImporter constructor with QT4 interface.

        This test only runs if PySide2 is available.
        """

        qt = qt_importer.QtImporter(qt_importer.QtImporter.QT4)

        # Check that the qt modules were initialized
        assert qt.QtCore
        assert qt.QtGui
        assert qt.QtNetwork
        assert qt.shiboken
        assert qt.shiboken.__name__ == "shiboken2"
        # We need one or the other
        assert qt.QtWebKit or qt.QtWebEngineWidgets

        # Expect PySide2 as the binding
        assert qt.binding_name == "PySide2"
        assert qt.base
        assert qt.base["__name__"] is qt.binding_name
        assert qt.base["__version__"] is qt.binding_version

    @skip_if_pyside2(found=False)
    def test_qt_importer_with_pyside2_interface_qt5(self):
        """
        Test the QtImporter constructor with QT5 interface.

        This test only runs if PySide2 is available.
        """

        qt = qt_importer.QtImporter(qt_importer.QtImporter.QT5)

        # Check that the qt modules were initialized
        assert qt.QtCore
        assert qt.QtGui
        assert qt.QtNetwork
        assert qt.shiboken
        assert qt.shiboken.__name__ == "shiboken2"
        try:
            qt_web_kit = qt.QtWebKit
        except KeyError:
            qt_web_kit = None
        try:
            qt_web_engine_widgets = qt.QtWebEngineWidgets
        except KeyError:
            qt_web_engine_widgets = None
        # We need one or the other
        assert qt_web_kit or qt_web_engine_widgets

        # Expect PySide2 as the binding
        assert qt.binding_name == "PySide2"
        assert qt.base
        assert qt.base["__name__"] is qt.binding_name
        assert qt.base["__version__"] is qt.binding_version

    @skip_if_pyside(found=False)
    @skip_if_pyside2(found=True)
    def test_qt_importer_with_pyside_interface_qt4(self):
        """
        Test the QtImporter constructor with default interface version requested.

        This test only runs if PySide is available and PySide2 is not available.
        """

        qt = qt_importer.QtImporter(qt_importer.QtImporter.QT4)

        # Check that the qt modules were initialized
        assert qt.QtCore
        assert qt.QtGui
        assert qt.QtNetwork
        assert qt.shiboken
        assert qt.shiboken.__name__ == "shiboken"
        # We need one or the other
        assert qt.QtWebKit or qt.QtWebEngineWidgets

        # Expect PySide2 as the binding
        assert qt.binding_name == "PySide"
        assert qt.base
        assert qt.base["__name__"] is qt.binding_name
        assert qt.base["__version__"] is qt.binding_version

    @skip_if_pyqt4(found=False)
    @skip_if_pyside(found=True)
    @skip_if_pyside2(found=True)
    def test_qt_importer_with_pyqt4_interface_qt4(self):
        """
        Test the QtImporter constructor with default interface version requested.

        This test only runs if PyQt4 is available and PySide, PySide2 are not available.
        """

        qt = qt_importer.QtImporter(qt_importer.QtImporter.QT4)

        # Check that the qt modules were initialized
        assert qt.QtCore
        assert qt.QtGui
        assert qt.QtNetwork
        assert qt.QtWebKit

        # Expect PySide2 as the binding
        assert qt.binding_name == "PyQt4"
        assert qt.base
        assert qt.base["__name__"] is qt.binding_name
        assert qt.base["__version__"] is qt.binding_version

    @skip_if_pyside6(found=False)
    @skip_if_pyqt4(found=True)
    @skip_if_pyside(found=True)
    @skip_if_pyside2(found=True)
    def test_qt_importer_with_pyside6_interface_qt4(self):
        """
        Test the QtImporter constructor with default interface version requested.

        This test only runs if PySide6 is available and PyQt4, PySide, PySide2 are not available.
        """

        qt = qt_importer.QtImporter(qt_importer.QtImporter.QT4)

        # Check that the qt modules were initialized
        assert qt.QtCore
        assert qt.QtGui
        assert qt.QtNetwork
        assert qt.shiboken
        assert qt.shiboken.__name__ == "shiboken6"
        # We need one or the other
        assert qt.QtWebKit or qt.QtWebEngineWidgets

        # Expect PySide2 as the binding
        assert qt.binding_name == "PySide6"
        assert qt.base
        assert qt.base["__name__"] is qt.binding_name
        assert qt.base["__version__"] is qt.binding_version

    @skip_if_pyside6(found=False)
    @skip_if_pyqt4(found=True)
    @skip_if_pyside(found=True)
    @skip_if_pyside2(found=True)
    def test_qt_importer_with_pyside6_interface_qt6(self):
        """
        Test the QtImporter constructor with default interface version requested.

        This test only runs if PySide6 is available and PyQt4, PySide, PySide2 are not available.
        """

        qt = qt_importer.QtImporter(qt_importer.QtImporter.QT6)

        # Check that the qt modules were initialized
        assert qt.QtCore
        assert qt.QtGui
        assert qt.QtNetwork
        assert qt.shiboken
        assert qt.shiboken.__name__ == "shiboken6"
        try:
            qt_web_kit = qt.QtWebKit
        except KeyError:
            qt_web_kit = None
        try:
            qt_web_engine_widgets = qt.QtWebEngineWidgets
        except KeyError:
            qt_web_engine_widgets = None
        # We need one or the other
        assert qt_web_kit or qt_web_engine_widgets

        # Expect PySide2 as the binding
        assert qt.binding_name == "PySide6"
        assert qt.base
        assert qt.base["__name__"] is qt.binding_name
        assert qt.base["__version__"] is qt.binding_version
