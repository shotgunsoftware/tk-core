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

from __future__ import with_statement

import re
import os
import sys
import functools
import imp
import subprocess
import webbrowser

from .. import constants
from .platforms import is_linux, is_macos, is_windows


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
    _core_to_qtgui = set(
        [
            "QAbstractProxyModel",
            "QItemSelection",
            "QItemSelectionModel",
            "QItemSelectionRange",
            "QSortFilterProxyModel",
            "QStringListModel",
        ]
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
    def _patch_QTextCodec(cls, QtCore):
        """
        Patches in QTextCodec.

        :param QTextCodec: The QTextCodec class.
        """
        original_QTextCodec = QtCore.QTextCodec

        class QTextCodec(original_QTextCodec):
            @staticmethod
            def setCodecForCStrings(codec):
                # Empty stub, doesn't exist in Qt5.
                pass

        QtCore.QTextCodec = QTextCodec

    @classmethod
    def _fix_QCoreApplication_api(cls, wrapper_class, original_class):

        # Enum values for QCoreApplication.translate's encode parameter.
        wrapper_class.CodecForTr = 0
        wrapper_class.UnicodeUTF8 = 1
        wrapper_class.DefaultCodec = wrapper_class.CodecForTr

        @staticmethod
        def translate(context, source_text, disambiguation=None, encoding=None, n=None):
            # In PySide2, the encoding argument has been deprecated, so we don't
            # pass it down. n is still supported however, but has always been optional
            # in PySide. So if n has been set to something, let's pass it down,
            # otherwise Qt5 has a default value for it, so we'll use that instead.
            if n is not None:
                return original_class.translate(context, source_text, disambiguation, n)
            else:
                return original_class.translate(context, source_text, disambiguation)

        wrapper_class.translate = translate

    @classmethod
    def _patch_QCoreApplication(cls, QtCore):
        """
        Patches QCoreApplication.

        :param QtCore: The QtCore module.
        """
        original_QCoreApplication = QtCore.QCoreApplication

        class QCoreApplication(original_QCoreApplication):
            pass

        cls._fix_QCoreApplication_api(QCoreApplication, original_QCoreApplication)
        QtCore.QCoreApplication = QCoreApplication

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

        # The some methods from the base class also need fixing, so do it.
        cls._fix_QCoreApplication_api(QApplication, original_QApplication)

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
            def __init__(self, *args):
                original_QStandardItemModel.__init__(self, *args)
                # Ideally we would only wrap the emit method but that attribute
                # is read only so we end up wrapping the whole object.
                self.dataChanged = SignalWrapper(self.dataChanged)

        QtGui.QStandardItemModel = QStandardItemModel

    @classmethod
    def _patch_QMessageBox(cls, QtGui):

        # Map for all the button types
        button_list = [
            QtGui.QMessageBox.Ok,
            QtGui.QMessageBox.Open,
            QtGui.QMessageBox.Save,
            QtGui.QMessageBox.Cancel,
            QtGui.QMessageBox.Close,
            QtGui.QMessageBox.Discard,
            QtGui.QMessageBox.Apply,
            QtGui.QMessageBox.Reset,
            QtGui.QMessageBox.RestoreDefaults,
            QtGui.QMessageBox.Help,
            QtGui.QMessageBox.SaveAll,
            QtGui.QMessageBox.Yes,
            QtGui.QMessageBox.YesToAll,
            QtGui.QMessageBox.No,
            QtGui.QMessageBox.NoToAll,
            QtGui.QMessageBox.Abort,
            QtGui.QMessageBox.Retry,
            QtGui.QMessageBox.Ignore,
        ]

        # PySide2 is currently broken and doesn't accept union of values in, so
        # we're building the UI ourselves as an interim solution.
        def _method_factory(icon, original_method):
            """
            Creates a patch for one of the static methods to pop a QMessageBox.
            """

            def patch(
                parent,
                title,
                text,
                buttons=QtGui.QMessageBox.Ok,
                defaultButton=QtGui.QMessageBox.NoButton,
            ):
                """
                Shows the dialog with, just like QMessageBox.{critical,question,warning,information} would do.

                :param title: Title of the dialog.
                :param text: Text inside the dialog.
                :param buttons: Buttons to show.
                :param defaultButton: Button selected by default.

                :returns: Code of the button selected.
                """
                msg_box = QtGui.QMessageBox(parent)
                msg_box.setWindowTitle(title)
                msg_box.setText(text)
                msg_box.setIcon(icon)
                for button in button_list:
                    if button & buttons:
                        msg_box.addButton(button)
                msg_box.setDefaultButton(defaultButton)
                msg_box.exec_()
                return msg_box.standardButton(msg_box.clickedButton())

            try:
                functools.update_wrapper(patch, original_method)
            except RuntimeError:
                # This is working around a bug in some versions of shiboken2
                # that we need to protect ourselves from. A true bug fix there
                # has been released in PySide2 5.13.x, but any DCCs we're
                # integrating with that embed the releases of 5.12.x with this
                # bug would break our integrations.
                #
                # Returning the patched method without decorating it via
                # update_wrapper doesn't cause us any harm, so it's safe to fall
                # back on this.
                pass

            return staticmethod(patch)

        original_QMessageBox = QtGui.QMessageBox

        class QMessageBox(original_QMessageBox):

            critical = _method_factory(
                QtGui.QMessageBox.Critical, QtGui.QMessageBox.critical
            )
            information = _method_factory(
                QtGui.QMessageBox.Information, QtGui.QMessageBox.information
            )
            question = _method_factory(
                QtGui.QMessageBox.Question, QtGui.QMessageBox.question
            )
            warning = _method_factory(
                QtGui.QMessageBox.Warning, QtGui.QMessageBox.warning
            )

        QtGui.QMessageBox = QMessageBox

    @classmethod
    def _patch_QDesktopServices(cls, QtGui, QtCore):

        # This is missing in certain versions of PySide 2. Add it in.
        if hasattr(QtGui, "QDesktopServices"):
            return

        class QDesktopServices(object):
            @classmethod
            def openUrl(cls, url):
                # Make sure we have a QUrl object.
                if not isinstance(url, QtCore.QUrl):
                    url = QtCore.QUrl(url)

                if url.isLocalFile():
                    url = url.toLocalFile().encode("utf-8")

                    if is_macos():
                        return subprocess.call(["open", url]) == 0
                    elif is_windows():
                        os.startfile(url)
                        # Start file returns None, so this is the best we can do.
                        return os.path.exists(url)
                    elif is_linux():
                        return subprocess.call(["xdg-open", url]) == 0
                    else:
                        raise ValueError("Unknown platform: %s" % sys.platform)
                else:
                    # According to webbrowser.py code logic, when open_new_tab() can find
                    # and launch a suitable browser, it returns True; otherwise it either
                    # returns False or raises some error.
                    try:
                        return webbrowser.open_new_tab(url.toString().encode("utf-8"))
                    except:
                        return False

            @classmethod
            def displayName(cls, type):
                cls.__not_implemented_error(cls.displayName)

            @classmethod
            def storageLocation(cls, type):
                cls.__not_implemented_error(cls.storageLocation)

            @classmethod
            def setUrlHandler(cls, scheme, receiver, method_name=None):
                cls.__not_implemented_error(cls.setUrlHandler)

            @classmethod
            def unsetUrlHandler(cls, scheme):
                cls.__not_implemented_error(cls.unsetUrlHandler)

            @classmethod
            def __not_implemented_error(cls, method):
                raise NotImplementedError(
                    "PySide2 and Toolkit don't support 'QDesktopServices.%s' yet. Please contact support at %s"
                    % (method.__func__, constants.SUPPORT_URL)
                )

        QtGui.QDesktopServices = QDesktopServices

    @classmethod
    def _patch_QWidget(cls, QtGui):
        original_QWidget_setContentsMargins = QtGui.QWidget.setContentsMargins
        original_QWidget_setStyleSheet = QtGui.QWidget.setStyleSheet
        original_QWidget_resize = QtGui.QWidget.resize

        re_css = re.compile("([0-9]+)\\s?(px)")

        def css_re_callback(matchobj):
            v = int(matchobj.group(1))
            return f"{v*2}px"

        class MyQWidget:
            def styleSheet(self, *args, **kwargs):
                return getattr(self, "orig_stylesheet_content", "")

            def setStyleSheet(self, *args, **kwargs):
                if len(args) == 1 and isinstance(args[0], str):
                    self.orig_stylesheet_content = args[0]

                    if "GLOBAL_DEBUG" in os.environ:
                        print("MyQWidget::setStyleSheet")
                        print(self.orig_stylesheet_content)
                    args = [re_css.sub(css_re_callback, args[0])]
                    if "GLOBAL_DEBUG" in os.environ:
                        print("  override css")
                        print(args[0])
                        print()

                return original_QWidget_setStyleSheet(self, *args, **kwargs)

            def resize(self, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQWidget::resize {args=}")
                if len(args) == 2 and isinstance(args[0], int) and isinstance(args[1], int):
                    self.orig_stylesheet_content = args[0]

                    args = [args[0]*2, args[1]*2]
                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"  override resize {args=}")

                return original_QWidget_resize(self, *args, **kwargs)

            def setContentsMargins(self, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQWidget::setContentsMargins {args=}")
                if len(args) == 4 and isinstance(args[0], int) and isinstance(args[1], int) and isinstance(args[2], int) and isinstance(args[3], int):
                    args = [args[0]*2, args[1]*2, args[2]*2, args[3]*2]
                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"  override {args=}")

                return original_QWidget_setContentsMargins(self, *args, **kwargs)

        QtGui.QWidget.setContentsMargins = MyQWidget.setContentsMargins
        QtGui.QWidget.styleSheet = MyQWidget.styleSheet
        QtGui.QWidget.setStyleSheet = MyQWidget.setStyleSheet
        QtGui.QWidget.resize = MyQWidget.resize

        original_QLayout_setContentsMargins = QtGui.QLayout.setContentsMargins
        original_QLayout_setSpacing = QtGui.QLayout.setSpacing
        original_QLayout_spacing = QtGui.QLayout.spacing

        class MyQLayout:
            def setContentsMargins(self, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQLayout::setContentsMargins {args=}")
                if len(args) == 4 and isinstance(args[0], int) and isinstance(args[1], int) and isinstance(args[2], int) and isinstance(args[3], int):
                    args = [args[0]*2, args[1]*2, args[2]*2, args[3]*2]
                    if "GLOBAL_DEBUG" in os.environ:
                       print(f"  override {args=}")

                return original_QLayout_setContentsMargins(self, *args, **kwargs)

            def setSpacing(self, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print("MyQLayout::setSpacing")
                if len(args) and isinstance(args[0], int):
                    self.orig_stylesheet_content = args[0]
                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"  override {args=}")
                    args = [args[0]*2, *args[1:]]

                return original_QLayout_setSpacing(self, *args, **kwargs)

            def spacing(self, *args, **kwargs):
                if hasattr(self, "orig_stylesheet_content"):
                    return self.orig_stylesheet_content
            
                return original_QLayout_spacing(self, *args, **kwargs)

        QtGui.QLayout.setContentsMargins = MyQLayout.setContentsMargins
        QtGui.QLayout.setSpacing = MyQLayout.setSpacing
        QtGui.QLayout.spacing = MyQLayout.spacing

    @classmethod
    def _patch_QHBoxLayout(cls, QtGui):
        original_QHBoxLayout = QtGui.QHBoxLayout

        class MyQHBoxLayout(original_QHBoxLayout):
            def setSpacing(self, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print()
                    print(f"MyQHBoxLayout::setSpacing {args=}")
                if len(args) and isinstance(args[0], int):
                    self.orig_stylesheet_content = args[0]
                    args = [args[0]*2, *args[1:]]
                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"  override {args=}")

                return original_QHBoxLayout.setSpacing(self, *args, **kwargs)

            def spacing(self, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQHBoxLayout::spacing {args=}")
                return original_QHBoxLayout.spacing(self, *args, **kwargs)

        QtGui.QHBoxLayout = MyQHBoxLayout

    @classmethod
    def _patch_QLabel(cls, QtGui):
        original_QLabel = QtGui.QLabel

        class MyQLabel(original_QLabel):
            def setMargin(self, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQLabel::setMargin {args=}")

                if len(args) and isinstance(args[0], int):
                    args = [args[0] * 2, *args[1:]]
                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"  override {args=}")

                return original_QLabel.setMargin(self, *args, **kwargs)

        QtGui.QLabel = MyQLabel

    @classmethod
    def _patch_QSize(cls, QtCore):
        original_QSize = QtCore.QSize

        class MyQSize(original_QSize):
            def __init__(self, *args):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQSize {args=}")

                if len(args) == 2 and isinstance(args[0], int) and isinstance(args[1], int):
                    args2x = args[0] * 2
                    args2y = args[1] * 2

                    if args2x >= 16777215:
                        args2x = args[0]

                    if args2y >= 16777215:
                        args2y = args[1]
                    
                    args = (args2x, args2y)
                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"   override {args=}")

                original_QSize.__init__(self, *args)

        QtCore.QSize = MyQSize

    @classmethod
    def _patch_QSpacerItem(cls, QtGui):
        original_QSpacerItem = QtGui.QSpacerItem

        class MyQSpacerItem(original_QSpacerItem):
            def __init__(self, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print()
                    print(f"MyQSpacerItem {args=}")

                if len(args) > 2 and isinstance(args[0], int) and isinstance(args[1], int):
                    args = [args[0] * 2, args[1] * 2, *args[2:]]
                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"  override {args=}")

                original_QSpacerItem.__init__(self, *args, **kwargs)

            def changeSize(self, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQSpacerItem::changeSize {args=}")

                if len(args) > 2 and isinstance(args[0], int) and isinstance(args[1], int):
                    args = [args[0] * 2, args[1] * 2, *args[2:]]
                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"  override {args=}")

                original_QSpacerItem.changeSize(self, *args, **kwargs)

        QtGui.QSpacerItem = MyQSpacerItem

    @classmethod
    def _patch_QPixmap(cls, QtGui):
        original_QPixmap_init = QtGui.QPixmap.__init__
        class MyQPixmap:
            def __init__(self, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print("MyQPixmap.__init__", args,  kwargs)

                return original_QPixmap_init(self, *args, **kwargs)

        QtGui.QPixmap.__init__ = MyQPixmap.__init__

    @classmethod
    def patch(cls, QtCore, QtGui, QtWidgets, PySide2):
        """
        Patches QtCore, QtGui and QtWidgets

        :param QtCore: The QtCore module.
        :param QtGui: The QtGui module.
        :param QtWidgets: The QtWidgets module.
        """

        print(f"PySide2Patcher::patch")

        qt_core_shim = imp.new_module("PySide.QtCore")
        qt_gui_shim = imp.new_module("PySide.QtGui")

        # Move everything from QtGui and QtWidgets unto the QtGui shim since
        # they belonged there in Qt 4.
        cls._move_attributes(qt_gui_shim, QtWidgets, dir(QtWidgets))
        cls._move_attributes(qt_gui_shim, QtGui, dir(QtGui))

        # Some classes from QtGui have been moved to QtCore, so put them back into QtGui
        cls._move_attributes(qt_gui_shim, QtCore, cls._core_to_qtgui)
        # Move the rest of QtCore in the new core shim.
        cls._move_attributes(
            qt_core_shim, QtCore, set(dir(QtCore)) - cls._core_to_qtgui
        )

        cls._patch_QTextCodec(qt_core_shim)
        cls._patch_QCoreApplication(qt_core_shim)
        cls._patch_QApplication(qt_gui_shim)
        cls._patch_QAbstractItemView(qt_gui_shim)
        cls._patch_QStandardItemModel(qt_gui_shim)
        if PySide2.__version_info__[0] < 5:
            # This patch is not needed in more recent versions of PySide2
            cls._patch_QMessageBox(qt_gui_shim)
        cls._patch_QDesktopServices(qt_gui_shim, qt_core_shim)

        ## TODO: do the same with:
        # setSpacing
        # setMargin
        # setStretch / setHorizontalStretch / setVerticalStretch ??
        # addSpacing(size)
        # addStretch([stretch=0])

        if "MyQWidget" in str(qt_gui_shim.QWidget.setStyleSheet):
            print("already hooked, nothing to do")
        else:
            cls._patch_QWidget(qt_gui_shim)

        cls._patch_QLabel(qt_gui_shim)
        cls._patch_QSize(qt_core_shim)
        cls._patch_QSpacerItem(qt_gui_shim)
        cls._patch_QHBoxLayout(qt_gui_shim)

        # print("Patcher run !!!")
        # print()

        #print("QDialog MRO 1:")
        # for i in QtWidgets.QDialog.mro():
        #     print("  ", i)
        # print()

        # print("QDialog MRO 2:")
        # for i in QtWidgets.QDialog.mro():
        #     print("  ", i)
        # print()

        # print("QWidget MRO 1:")
        # for i in qt_gui_shim.QWidget.mro():
        #     print("  ", i)
        # print()

        # print("PySide2.QtWidgets.QWidget:", PySide2.QtWidgets.QWidget)
        # print("qt_gui_shim.QWidget      :", qt_gui_shim.QWidget

        return qt_core_shim, qt_gui_shim
