# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from .pyside2_patcher import PySide2Patcher


class PyQt5Patcher(PySide2Patcher):
    """
    Patches PyQt5 so it can be API compatible with PySide 1.

    Credit to Diego Garcia Huerta for the work done in tk-krita:
    https://github.com/diegogarciahuerta/tk-krita/blob/80544f1b40702d58f0378936532d8e25f9981e65/engine.py

    .. code-block:: python
        from PyQt5 import QtGui, QtCore, QtWidgets
        import PyQt5
        PyQt5Patcher.patch(QtCore, QtGui, QtWidgets, PyQt5)
    """

    # Flag that will be set at the module level so that if an engine is reloaded
    # the PySide 2 API won't be monkey patched twice.

    # Note: not sure where this is in use in SGTK, but wanted to make sure
    # nothing breaks
    _TOOLKIT_COMPATIBLE = "__toolkit_compatible"

    @classmethod
    def patch(cls, QtCore, QtGui, QtWidgets, PyQt5):
        """
        Patches QtCore, QtGui and QtWidgets
        :param QtCore: The QtCore module.
        :param QtGui: The QtGui module.
        :param QtWidgets: The QtWidgets module.
        :param PyQt5: The PyQt5 module.
        """

        # Add this version info otherwise it breaks since tk_core v0.19.9
        # PySide2Patcher is now checking the version of PySide2 in a way
        # that PyQt5 does not like: __version_info__ is not defined in PyQt5
        version = list(map(int, QtCore.PYQT_VERSION_STR.split(".")))
        PyQt5.__version_info__ = version

        QtCore, QtGui = PySide2Patcher.patch(QtCore, QtGui, QtWidgets, PyQt5)

        def SIGNAL(arg):
            """
            This is a trick to fix the fact that old style signals are not
            longer supported in pyQt5
            """
            return arg.replace("()", "")

        class QLabel(QtGui.QLabel):
            """
            Unfortunately in some cases sgtk sets the pixmap as None to remove
            the icon. This behaviour is not supported in PyQt5 and requires
            an empty instance of QPixmap.
            """

            def setPixmap(self, pixmap):
                if pixmap is None:
                    pixmap = QtGui.QPixmap()
                return super(QLabel, self).setPixmap(pixmap)

        class QPixmap(QtGui.QPixmap):
            """
            The following method is obsolete in PyQt5 so we have to provide
            a backwards compatible solution.
            https://doc.qt.io/qt-5/qpixmap-obsolete.html#grabWindow
            """

            def grabWindow(self, window, x=0, y=0, width=-1, height=-1):
                screen = QtGui.QApplication.primaryScreen()
                return screen.grabWindow(window, x=x, y=y, width=width, height=height)

        class QAction(QtGui.QAction):
            """
            From the docs:
            https://www.riverbankcomputing.com/static/Docs/PyQt5/incompatibilities.html#qt-signals-with-default-arguments
            Explanation:
            https://stackoverflow.com/questions/44371451/python-pyqt-qt-qmenu-qaction-syntax
            A lot of cases in tk apps where QAction triggered signal is
            connected with `triggered[()].connect` which in PyQt5 is a problem
            because triggered is an overloaded signal with two signatures,
            triggered = QtCore.pyqtSignal(bool)
            triggered = QtCore.pyqtSignal()
            If you wanted to use the second overload, you had to use the
            `triggered[()]` approach to avoid the extra boolean attribute to
            trip you in the callback function.
            The issue is that in PyQt5.3+ this has changed and is no longer
            allowed as only the first overloaded function is implemented and
            always called with the extra boolean value.
            To avoid this normally we would have to decorate our slots with the
            decorator:
            @QtCore.pyqtSlot
            but changing the tk apps is out of the scope of this engine.
            To fix this we implement a new signal and rewire the connections so
            it is available once more for tk apps to be happy.
            """

            triggered_ = QtCore.pyqtSignal([bool], [])

            def __init__(self, *args, **kwargs):
                super(QAction, self).__init__(*args, **kwargs)
                super(QAction, self).triggered.connect(lambda checked: self.triggered_[()])
                super(QAction, self).triggered.connect(self.triggered_[bool])
                self.triggered = self.triggered_
                self.triggered.connect(self._onTriggered)

            def _onTriggered(self, checked=False):
                self.triggered_[()].emit()

        class QAbstractButton(QtGui.QAbstractButton):
            """ See QAction above for explanation """

            clicked_ = QtCore.pyqtSignal([bool], [])
            triggered_ = QtCore.pyqtSignal([bool], [])

            def __init__(self, *args, **kwargs):
                super(QAbstractButton, self).__init__(*args, **kwargs)
                super(QAbstractButton, self).clicked.connect(lambda checked: self.clicked_[()])
                super(QAbstractButton, self).clicked.connect(self.clicked_[bool])
                self.clicked = self.clicked_
                self.clicked.connect(self._onClicked)

                super(QAction, self).triggered.connect(lambda checked: self.triggered_[()])
                super(QAction, self).triggered.connect(self.triggered_[bool])
                self.triggered = self.triggered_
                self.triggered.connect(self._onTriggered)

            def _onClicked(self, checked=False):
                self.clicked_[()].emit()

        class QObject(QtCore.QObject):
            """
            QObject no longer has got the connect method in PyQt5 so we have to
            reinvent it here...
            https://doc.bccnsoft.com/docs/PyQt5/pyqt4_differences.html#old-style-signals-and-slots
            """

            def connect(self, sender, signal, method, connection_type=QtCore.Qt.AutoConnection):
                if hasattr(sender, signal):
                    getattr(sender, signal).connect(method, connection_type)

        class QCheckBox(QtGui.QCheckBox):
            """
            PyQt5 no longer allows anything but an QIcon as an argument. In some
            cases sgtk is passing a pixmap, so we need to intercept the call to
            convert the pixmap to an actual QIcon.
            """

            def setIcon(self, icon):
                return super(QCheckBox, self).setIcon(QtGui.QIcon(icon))

        class QTabWidget(QtGui.QTabWidget):
            """
            For whatever reason pyQt5 is returning the name of the Tab
            including the key accelerator, the & that indicates what key is
            the shortcut. This is tripping dialog.py in tk-multi-loaders2
            """

            def tabText(self, index):
                return super(QTabWidget, self).tabText(index).replace("&", "")

        class QPyTextObject(QtCore.QObject, QtGui.QTextObjectInterface):
            """
            PyQt4 implements the QPyTextObject as a workaround for the inability
            to define a Python class that is sub-classed from more than one Qt
            class. QPyTextObject is not implemented in PyQt5
            https://doc.bccnsoft.com/docs/PyQt5/pyqt4_differences.html#qpytextobject
            """

            pass

        class QStandardItem(QtGui.QStandardItem):
            """
            PyQt5 no longer allows anything but an QIcon as an argument. In some
            cases sgtk is passing a pixmap, so we need to intercept the call to
            convert the pixmap to an actual QIcon.
            """

            def setIcon(self, icon):
                icon = QtGui.QIcon(icon)
                return super(QStandardItem, self).setIcon(icon)

        class QTreeWidgetItem(QtGui.QTreeWidgetItem):
            """
            PyQt5 no longer allows anything but an QIcon as an argument. In some
            cases sgtk is passing a pixmap, so we need to intercept the call to
            convert the pixmap to an actual QIcon.
            """

            def setIcon(self, column, icon):
                icon = QtGui.QIcon(icon)
                return super(QTreeWidgetItem, self).setIcon(column, icon)

        class QTreeWidgetItemIterator(QtGui.QTreeWidgetItemIterator):
            """
            This fixes the iteration over QTreeWidgetItems. It seems that it is
            no longer iterable, so we create our own.
            """

            def __iter__(self):
                value = self.value()
                while value:
                    yield self
                    self += 1
                    value = self.value()

        class QColor(QtGui.QColor):
            """
            Adds missing toTuple method to PyQt5 QColor class.
            """
            def toTuple(self):
                if self.spec() == QtGui.QColor.Rgb:
                    r, g, b, a = self.getRgb()
                    return (r, g, b, a)
                elif self.spec() == QtGui.QColor.Hsv:
                    h, s, v, a = self.getHsv()
                    return (h, s, v, a)
                elif self.spec() == QtGui.QColor.Cmyk:
                    c, m, y, k, a = self.getCmyk()
                    return (c, m, y, k, a)
                elif self.spec() == QtGui.QColor.Hsl:
                    h, s, l, a = self.getHsl()
                    return (h, s, l, a)
                return tuple()

        # hot patch the library to make it work with pyside code
        QtCore.SIGNAL = SIGNAL
        QtCore.Signal = QtCore.pyqtSignal
        QtCore.Slot = QtCore.pyqtSlot
        QtCore.Property = QtCore.pyqtProperty
        QtCore.__version__ = QtCore.PYQT_VERSION_STR

        # widgets and class fixes
        QtGui.QLabel = QLabel
        QtGui.QPixmap = QPixmap
        QtGui.QAction = QAction
        QtCore.QObject = QObject
        QtGui.QCheckBox = QCheckBox
        QtGui.QTabWidget = QTabWidget
        QtGui.QStandardItem = QStandardItem
        QtGui.QPyTextObject = QPyTextObject
        QtGui.QTreeWidgetItem = QTreeWidgetItem
        QtGui.QTreeWidgetItemIterator = QTreeWidgetItemIterator
        QtGui.QColor = QColor

        return QtCore, QtGui
