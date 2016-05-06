# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Shims for different versions of PySide and PyQt that converts their api
to be compatible with PySide1.
"""


def _create_shim_dict(core, gui, base_dialog, module):
    """
    Creates a shim dictionary with keys named appropriately.
    """
    return {
        "qt_core": core,
        "qt_gui": gui,
        "dialog_base": base_dialog,
        "wrapper": module
    }


def _create_pyside_shim():
    """
    Creates a shim for PySide
    """
    import PySide
    from PySide import QtCore, QtGui
    # Some old versions of PySide don't include version information
    # so add something here so that we can use PySide.__version__ 
    # later without having to check!
    if not hasattr(PySide, "__version__"):
        PySide.__version__ = "<unknown>"

    return _create_shim_dict(QtCore, QtGui, QtGui.QDialog, PySide)


def _create_pyside2_shim():
    """
    Creates a shim for PySide2
    """
    import PySide2
    from PySide2 import QtCore, QtGui, QtWidgets
    from .pyside2_patcher import PySide2Patcher

    PySide2Patcher.patch(QtCore, QtGui, QtWidgets, PySide2)

    return _create_shim_dict(QtCore, QtGui, QtGui.QDialog, PySide2)


def _create_pyqt4_shim():
    """
    Creates a shim for PyQt4
    """
    from PyQt4 import QtCore, QtGui
    from blurdev.gui import Dialog

    # hot patch the library to make it work with pyside code
    QtCore.Signal = QtCore.pyqtSignal
    QtCore.Slot = QtCore.pyqtSlot
    QtCore.Property = QtCore.pyqtProperty

    # dialog wrapper needs to be the blurdev dialog
    return _create_shim_dict(QtCore, QtGui, Dialog)


def create_shim():
    """
    Creates a Qt shim compatible with PySide 1.
    """
    try:
        return _create_pyside2_shim()
    except ImportError:
        pass

    try:
        return _create_pyside_shim()
    except ImportError:
        pass

    return _create_pyqt4_shim()
