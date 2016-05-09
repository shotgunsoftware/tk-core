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
Patches for different versions of Qt.
"""


class PySide2Patcher(object):
    """
    Patches PySide 2 so it can be API compatible with PySide 1.
    """

    _core_to_qtgui = (
        "QAbstractProxyModel",
        "QItemSelection",
        "QItemSelectionModel",
        "QItemSelectionRange",
        "QSortFilterProxyModel",
        "QStringListModel"
    )

    _TOOLKIT_COMPATIBLE = "__toolkit_compatible"

    @classmethod
    def _move_attributes(cls, dst, src, names):
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
        translate = QCoreApplication.translate

        @staticmethod
        def wrapper(context, source_text, disambiguation=None, encoding=None, n=None):
            # In PySide2, the encoding argument has been deprecated, so we don't
            # pass it down. n is still supported however, but has always been optional
            # in PySide. So if n has been set to something, let's pass it down,
            # otherwise Qt5 has a default value for it, so we'll use that instead.
            if n is not None:
                return translate(context, source_text, disambiguation, n)
            else:
                return translate(context, source_text, disambiguation)

        QCoreApplication.translate = wrapper

        QCoreApplication.CodecForTr = 0
        QCoreApplication.UnicodeUTF8 = 1
        QCoreApplication.DefaultCodec = QCoreApplication.CodecForTr

    @classmethod
    def _patch_QApplication(cls, QtGui):
        """
        Patches QApplication.

        :param QtGui: QtGui module.
        """
        QApplication = QtGui.QApplication

        class Wrapper(QApplication):
            def __init__(self, *args):
                QApplication.__init__(self, *args)
                # qApp has been moved from QtGui to QtWidgets, make sure that
                # when QApplication is instantiated than qApp is set on QtGui.
                QtGui.qApp = self

            @staticmethod
            def palette():
                # Retrieve the application palette by passing no widget.
                return QApplication.palette(None)

        QtGui.QApplication = Wrapper

    @classmethod
    def _patch_QAbstractItemView(cls, QtGui):
        """
        Patches QAbstractItemView.

        :param QtGui: QtGui module.
        """
        QAbstractItemView = QtGui.QAbstractItemView

        class Wrapper(QAbstractItemView):
            def __init__(self, *args):
                QAbstractItemView.__init__(self, *args)
                # dataChanged's signature has an extra parameter in Qt5. Since this
                # is a virtual method than is usually overriden, monkey patch
                # this object's dataChanged if present to Qt can invoke the Python
                # version and then forward the call back to the derived class's
                # implementation.
                if hasattr(self, "dataChanged"):
                    dataChanged = self.dataChanged
                    self.dataChanged = lambda tl, br, roles: dataChanged(tl, br)

        QtGui.QAbstractItemView = Wrapper

    @classmethod
    def _patch_QStandardItemModel(cls, QtGui):

        QStandardItemModel = QtGui.QStandardItemModel

        class SignalWrapper(object):
            def __init__(self, signal):
                self._signal = signal

            def emit(self, tl, br):
                self._signal.emit(tl, br, [])

            def __getattr__(self, name):
                # Forward to the wrapped object.
                return getattr(self._signal, name)

        class Wrapper(QStandardItemModel):
            def __init__(self, *args):
                QStandardItemModel.__init__(self, *args)
                # Ideally we would only wrap the emit method but that attibute
                # is read only so we end up wrapping the whole object.
                self.dataChanged = SignalWrapper(self.dataChanged)

        QtGui.QStandardItemModel = Wrapper

    @classmethod
    def patch(cls, QtCore, QtGui, QtWidgets, PySide2):
        """
        Patches QtCore, QtGui and QtWidgets

        :param QtCore: The QtCore module.
        :param QtGui: The QtGui module.
        :param QtWidgets: The QtWidgets module.
        """
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

        setattr(PySide2, cls._TOOLKIT_COMPATIBLE, True)
