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
Qt version abstraction layer.
"""


class QtImporter(object):
    """
    Imports different versions of Qt and makes their API compatible with PySide.

    .. code-block:: python
        try:
            importer = QtImporter()
        except Exception as e:
            print "Couldn't import a Qt Wrapper: " % (e,)
        else:
            importer.QtGui.QApplication([])
            ...
    """

    def __init__(self):
        """
        Imports the Qt modules and sets the QtCore, QtGui and wrapper attributes
        on this object.
        """
        self.QtCore, self.QtGui, self.wrapper, self.qt_version_tuple = self._import_modules()

    def _import_pyside(self):
        """
        Imports PySide.

        :returns: The (QtCore, QtGui, PySide) tuple.
        """
        import PySide
        from PySide import QtCore, QtGui
        # Some old versions of PySide don't include version infor   tion
        # so add something here so that we can use PySide.__version__
        # later without having to check!
        if not hasattr(PySide, "__version__"):
            PySide.__version__ = "<unknown>"

        return QtCore, QtGui, PySide, self._to_version_tuple(QtCore.qVersion())

    def _import_pyside2(self):
        """
        Imports PySide2.

        :returns: The (QtCore, QtGui, PySide2) tuple.
        """
        import PySide2
        from PySide2 import QtCore, QtGui, QtWidgets
        from .pyside2_patcher import PySide2Patcher

        QtCore, QtGui, PySide2 = PySide2Patcher.patch(QtCore, QtGui, QtWidgets, PySide2)
        return QtCore, QtGui, PySide2, self._to_version_tuple(QtCore.qVersion())

    def _import_pyqt4(self):
        """
        Imports PyQt4.

        :returns: The (QtCore, QtGui, PyQt4) tuple.
        """
        import PyQt4
        from PyQt4 import QtCore, QtGui

        # hot patch the library to make it work with pyside code
        QtCore.Signal = QtCore.pyqtSignal
        QtCore.Slot = QtCore.pyqtSlot
        QtCore.Property = QtCore.pyqtProperty

        from PyQt4.Qt import PYQT_VERSION_STR
        PyQt4.__version__ = PYQT_VERSION_STR

        return QtCore, QtGui, PyQt4, self._to_version_tuple(QtCore.QT_VERSION_STR)

    def _import_modules(self):
        """
        Tries to import different Qt wrapper implementation in the following order:
            - PySide 2
            - PySide
            - PyQt4

        :returns: The (QtCore, QtGui, PySide2|PySide|PyQt4) tuple.
        """
        try:
            return self._import_pyside2()
        except ImportError:
            pass

        try:
            return self._import_pyside()
        except ImportError:
            pass

        try:
            return self._import_pyqt4()
        except ImportError:
            return (None, None, None, None)

    def _to_version_tuple(self, version_str):
        """
        Converts a version string with the dotted notation into a tuple
        of integers.

        :param version_str: Version string to convert.

        :returns: A tuple of integer representing the version.
        """
        return tuple([int(c) for c in version_str.split(".")])
