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
PySide 2 backwards compatibility layer for use with PySide 1 code.
"""


class PySide2Patcher(object):
    """
    Patches PySide 2 so it can be API compatible with PySide 1.

    .. code-block:: python
        from PySide2 import QtGui, QtCore, QtWidgets
        import PySide2
        PySide2Patcher.patch(QtCore, QtGui, QtWidgets, PySide2)
    """

    # These classes have been moved from QtGui in Qt4 to QtCore in Qt5 and we're
    # moving them back from QtCore to QtGui to preserve backward compability with
    # PySide 1.
    _core_to_qtgui = (
        "QAbstractProxyModel",
        "QItemSelection",
        "QItemSelectionModel",
        "QItemSelectionRange",
        "QSortFilterProxyModel",
        "QStringListModel"
    )

    # Flag that will be set at the module level so that if an engine is reloaded
    # the PySide 2 API won't be monkey patched twice.
    _TOOLKIT_COMPATIBLE = "__toolkit_compatible"

    @classmethod
    def _move_attributes(cls, dst, src, names):
        """
        Moves a list of attributes from one package to another.

        :param names: Names of the attributes to move.
        """
        for name in names:
            if not hasattr(dst, name):
                setattr(dst, name, getattr(src, name))

    @classmethod
    def _patch_QTextCodec(cls, QTextCodec):
        """
        Patches in QTextCodec.

        :param QTextCodec: The QTextCodec class.
        """
        @staticmethod
        def setCodecForCStrings(codec):
            # Empty stub, doesn't exist in Qt5.
            pass

        QTextCodec.setCodecForCStrings = setCodecForCStrings

    @classmethod
    def _patch_QCoreApplication(cls, QCoreApplication):
        """
        Patches QCoreApplication.

        :param QCoreApplication: The QCoreApplication class.
        """
        original_translate = QCoreApplication.translate

        @staticmethod
        def translate(context, source_text, disambiguation=None, encoding=None, n=None):
            # In PySide2, the encoding argument has been deprecated, so we don't
            # pass it down. n is still supported however, but has always been optional
            # in PySide. So if n has been set to something, let's pass it down,
            # otherwise Qt5 has a default value for it, so we'll use that instead.
            if n is not None:
                return original_translate(context, source_text, disambiguation, n)
            else:
                return original_translate(context, source_text, disambiguation)

        QCoreApplication.translate = translate

        # Enum values for QCoreApplication.translate's encode parameter.
        QCoreApplication.CodecForTr = 0
        QCoreApplication.UnicodeUTF8 = 1
        QCoreApplication.DefaultCodec = QCoreApplication.CodecForTr

    @classmethod
    def _patch_QApplication(cls, QtGui):
        """
        Patches QApplication.

        :param QtGui: QtGui module.
        """
        original_QApplication = QtGui.QApplication

        class QApplication(original_QApplication):
            def __init__(self, *args):
                original_QApplication.__init__(self, *args)
                # qApp has been moved from QtGui to QtWidgets, make sure that
                # when QApplication is instantiated than qApp is set on QtGui.
                QtGui.qApp = self

            @staticmethod
            def palette(widget=None):
                # PySide 1 didn't take a parameter for this method.
                # Retrieve the application palette by passing no widget.
                return original_QApplication.palette(widget)

        QtGui.QApplication = QApplication

    @classmethod
    def _patch_QAbstractItemView(cls, QtGui):
        """
        Patches QAbstractItemView.

        :param QtGui: QtGui module.
        """
        original_QAbstractItemView = QtGui.QAbstractItemView

        class QAbstractItemView(original_QAbstractItemView):
            def __init__(self, *args):
                original_QAbstractItemView.__init__(self, *args)
                # dataChanged's is a virtual method whose signature has an extra
                # parameter in Qt5. This method can be called from the C++ side
                # and it expects to be able to pass in arguments. We'll monkey patch
                # this object's dataChanged, if present, so Qt can invoke the Python
                # version and then forward the call back to the derived class's
                # implementation. Roles is allowed to be optional so that any
                # PySide1 code can still invoke the dataChanged method.
                if hasattr(self, "dataChanged"):
                    original_dataChanged = self.dataChanged

                    def dataChanged(tl, br, roles=None):
                        original_dataChanged(tl, br)
                    self.dataChanged = lambda tl, br, roles: dataChanged(tl, br)

        QtGui.QAbstractItemView = QAbstractItemView

    @classmethod
    def _patch_QStandardItemModel(cls, QtGui):

        original_QStandardItemModel = QtGui.QStandardItemModel

        class SignalWrapper(object):
            def __init__(self, signal):
                self._signal = signal

            def emit(self, tl, br):
                self._signal.emit(tl, br, [])

            def __getattr__(self, name):
                # Forward to the wrapped object.
                return getattr(self._signal, name)

        class QStandardItemModel(original_QStandardItemModel):
            def original_QStandardItemModel(self, *args):
                QStandardItemModel.__init__(self, *args)
                # Ideally we would only wrap the emit method but that attibute
                # is read only so we end up wrapping the whole object.
                self.dataChanged = SignalWrapper(self.dataChanged)

        QtGui.QStandardItemModel = QStandardItemModel

    @classmethod
    def _patch_QMessageBox(cls, QMessageBox):

        # Map for all the button types
        button_list = [
            QMessageBox.Ok,
            QMessageBox.Open,
            QMessageBox.Save,
            QMessageBox.Cancel,
            QMessageBox.Close,
            QMessageBox.Discard,
            QMessageBox.Apply,
            QMessageBox.Reset,
            QMessageBox.RestoreDefaults,
            QMessageBox.Help,
            QMessageBox.SaveAll,
            QMessageBox.Yes,
            QMessageBox.YesAll,
            QMessageBox.YesToAll,
            QMessageBox.No,
            QMessageBox.NoAll,
            QMessageBox.NoToAll,
            QMessageBox.Abort,
            QMessageBox.Retry,
            QMessageBox.Ignore
        ]

        # PySide2 is currently broken and doesn't accept union of values in, so
        # we're building the UI ourselves as an interim solution.
        def _patch_factory(icon):
            """
            Creates a patch for one of the static methods to pop a QMessageBox.
            """
            def patch(parent, title, text, buttons=QMessageBox.Ok, defaultButton=QMessageBox.NoButton):
                """
                Shows the dialog with, just like QMessageBox.{critical,question,warning,information} would do.

                :param title: Title of the dialog.
                :param text: Text inside the dialog.
                :param buttons: Buttons to show.
                :param defaultButton: Button selected by default.

                :returns: Code of the button selected.
                """
                msg_box = QMessageBox(parent)
                msg_box.setWindowTitle(title)
                msg_box.setText(text)
                msg_box.setIcon(icon)
                for button in button_list:
                    if button & buttons:
                        msg_box.addButton(button)
                msg_box.setDefaultButton(defaultButton)
                msg_box.exec_()
                return msg_box.standardButton(msg_box.clickedButton())
            return staticmethod(patch)

        QMessageBox.critical = _patch_factory(QMessageBox.Critical)
        QMessageBox.information = _patch_factory(QMessageBox.Information)
        QMessageBox.question = _patch_factory(QMessageBox.Question)
        QMessageBox.warning = _patch_factory(QMessageBox.Warning)

    @classmethod
    def patch(cls, QtCore, QtGui, QtWidgets, PySide2):
        """
        Patches QtCore, QtGui and QtWidgets

        :param QtCore: The QtCore module.
        :param QtGui: The QtGui module.
        :param QtWidgets: The QtWidgets module.
        """
        # Make sure the API hasn't already been patched.
        if hasattr(PySide2, cls._TOOLKIT_COMPATIBLE):
            return

        # Qt5 has moved some classes around, move them back into place.
        cls._move_attributes(QtGui, QtWidgets, dir(QtWidgets))
        cls._move_attributes(QtGui, QtCore, cls._core_to_qtgui)

        cls._patch_QTextCodec(QtCore.QTextCodec)
        cls._patch_QCoreApplication(QtCore.QCoreApplication)
        cls._patch_QApplication(QtGui)
        cls._patch_QAbstractItemView(QtGui)
        cls._patch_QStandardItemModel(QtGui)
        cls._patch_QMessageBox(QtGui.QMessageBox)

        # Indicate the API has been patched.
        setattr(PySide2, cls._TOOLKIT_COMPATIBLE, True)
