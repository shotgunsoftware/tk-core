import imp
import sys

class PySide6Patcher:
    _core_to_qtgui = {
        "QStringListModel",
        "QStringList",
        "QTextStream",
        "QTextStreamManipulator",
        "QTextCodec",
        "QTextCodecConverter",
        "QTextDecoder",
        "QTextEncoder",
        "QTextStreamReader",
        "QTextStreamWriter",
    }

    @classmethod
    def patch(cls, QtCore, QtGui, QtWidgets, PySide2):
        """
        Patches PySide2 to make it compatible with PySide6.

        :param QtCore: The QtCore module.
        :param QtGui: The QtGui module.
        :param QtWidgets: The QtWidgets module.
        :param PySide2: The PySide2 module.
        """
        qt_core_shim = imp.new_module("PySide6.QtCore")
        qt_gui_shim = imp.new_module("PySide6.QtGui")

        # Move everything from QtGui and QtWidgets to the QtGui shim since they belonged there
        # in PySide6.
        cls._move_attributes(qt_gui_shim, QtWidgets, dir(QtWidgets))
        cls._move_attributes(qt_gui_shim, QtGui, dir(QtGui))

        # Some classes from QtGui have been moved to QtCore, so put them back into QtGui
        cls._move_attributes(qt_gui_shim, QtCore, cls._core_to_qtgui)
        # Move the rest of QtCore in the new core shim.
        cls._move_attributes(
            qt_core_shim, QtCore, set(dir(QtCore)) - cls._core_to_qtgui
        )

        # Move QtWebEngineWidgets to the QtGui shim
        qt_webengine_widgets = imp.new_module("PySide6.QtWebEngineWidgets")
        cls._move_attributes(qt_webengine_widgets, PySide2.QtWebEngineWidgets, dir(PySide2.QtWebEngineWidgets))
        sys.modules["PySide6.QtWebEngineWidgets"] = qt_webengine_widgets

        # Move QtNetwork to the QtCore shim
        qt_network = imp.new_module("PySide6.QtNetwork")
        cls._move_attributes(qt_network, PySide2.QtNetwork, dir(PySide2.QtNetwork))
        sys.modules["PySide6.QtNetwork"] = qt_network

        # Move shiboken2 to the PySide6 module
        sys.modules["PySide6.shiboken2"] = PySide2.shiboken2

        # ... other necessary patches ...

        return qt_core_shim, qt_gui_shim

    @classmethod
    def _move_attributes(cls, dst, src, attributes):
        for attr in attributes:
            setattr(dst, attr, getattr(src, attr))

    @classmethod
    def _patch_QModelIndex(cls, QtCore):
        """Patch QModelIndex."""

        def child(self, row, column):
            """Patch the child method."""

            return self.model().index(row, column, self)

        QtCore.QModelIndex.child = child

    @classmethod
    def _patch_QAbstractItemView(cls, QtGui):
        """Patch QAbstractItemView."""

        def viewOptions(self):
            """Patch the viewOptions method."""

            option = QtGui.QStyleOptionViewItem()
            self.initViewItemOption(option)
            return option

        QtGui.QAbstractItemView.viewOptions = viewOptions

    @classmethod
    def _patch_QTextCodec(cls, QtCore):
        """Patch QTextCodec."""

        def codecForName(name):
            """Patch the codecForName method."""

            return QtCore.QTextCodec.codecForName(name)

        QtCore.QTextCodec.codecForName = codecForName

    # @classmethod
    # def _patch_QApplication(cls, QtGui):
    #     """Patch QApplication."""

    #     def notify(self, receiver, event):
    #         """Patch the notify method."""

    #         return self.notify(receiver, event)

    #     QtGui.QApplication.notify = notify

    @classmethod
    def _patch_QDesktopServices(cls, QtGui, QtCore):
        """Patch QDesktopServices."""

        def openUrl(self, url):
            """Patch the openUrl method."""

            return self.openUrl(url)

        QtGui.QDesktopServices.openUrl = openUrl

    @classmethod
    def _patch_QMessageBox(cls, QtGui):
        """Patch QMessageBox."""

        def information(self, parent, title, text, buttons, defaultButton):
            """Patch the information method."""

            return self.information(parent, title, text, buttons, defaultButton)

        QtGui.QMessageBox.information = information

    @classmethod
    def _patch_QScreen(cls, QtCore, QtGui):
        """Patch QScreen."""

        def availableGeometry(self):
            """Patch the availableGeometry method."""

            return self.availableGeometry()

        QtCore.QScreen.availableGeometry