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
Shims for different versions of PySide and PyQt
"""

_core_to_qtgui = (
    "QAbstractProxyModel",
    "QItemSelection",
    "QItemSelectionModel",
    "QItemSelectionRange",
    "QSortFilterProxyModel",
    "QStringListModel"
)
_multimedia_to_qtgui = ("QSound",)
_extras_to_qtgui = ("QX11Info",)

def _create_shim_dict(core, gui, base_dialog):
    """
    Creates a shim dictionary with keys named appropriately.
    """
    return {
        "qt_core": core
        "qt_gui": gui
        "dialog_base": base_dialog
    }

def _move_attributes(dst, src, names):
    for name in names:
        if not hasattr(dst, name):
            setattr(dst, name, getattr(src, name))

def create_shim():
    """
    Creates a shim with the version of the Qt library available.
    """
    try:
        from PySide import QtCore, QtGui
        return _create_shim_dict(QtCore, QtGui, QtGui.QDialog)
    except ImportError:
        pass

    try:
        from PySide2 import QtCore, QtGui, QtWidgets, QtPrintSupport, QtMultimedia

        _move_attributes(QtGui, QtWidgets, dir(QtWidgets))
        _move_attributes(QtGui, QtPrintSupport, dir(QtPrintSupport))
        _move_attributes(QtGui, QtCore, _core_to_qtgui)
        _move_attributes(QtGui, QtMultimedia, _multimedia_to_qtgui)

        try:
            from PySide2 import QtX11Extras
        except ImportError:
            pass
        else:
            _move_attributes(QtGui, QtX11Extras, _extras_to_qtgui)

        # define UnicodeUTF8 to be compatible with the new signature to QApplication.translate
        QtGui.QApplication.UnicodeUTF8 = -1

        return _create_shim_dict(QtCore, QtGui, QtGui.QDialog)

    except ImportError:
        pass

    from PyQt4 import QtCore, QtGui
    from blurdev.gui import Dialog

    # hot patch the library to make it work with pyside code
    QtCore.Signal = QtCore.pyqtSignal
    QtCore.Slot = QtCore.pyqtSlot
    QtCore.Property = QtCore.pyqtProperty

    # dialog wrapper needs to be the blurdev dialog
    return _create_shim_dict(QtCore, QtGui, Dialog)
