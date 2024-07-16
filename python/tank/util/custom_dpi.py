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


class DPIQtPatcher(object):

    # Flag that will be set at the module level so that if an engine is reloaded
    # the PySide 2 API won't be monkey patched twice.
    _TOOLKIT_COMPATIBLE = "__toolkit_compatible"


    @classmethod
    def process(cls):
        """
        Patches QtCore, QtGui and QtWidgets

        :param QtCore: The QtCore module.
        :param QtGui: The QtGui module.
        :param QtWidgets: The QtWidgets module.
        """

        print(f"PySide2Patcher::patch")

        qt_core_shim = imp.new_module("PySide.QtCore")
        qt_gui_shim = imp.new_module("PySide.QtGui")



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

        # cls._patch_QLabel(qt_gui_shim)
        cls._patch_QSize(qt_core_shim)
        cls._patch_QPoint(qt_core_shim)
        cls._patch_QRect(qt_core_shim)
        # cls._patch_QSpacerItem(qt_gui_shim)
        # cls._patch_QHBoxLayout(qt_gui_shim)


        return qt_core_shim, qt_gui_shim





    @classmethod
    def _patch_QWidget(cls, QtGui):
        original_QWidget_setContentsMargins = QtGui.QWidget.setContentsMargins
        original_QWidget_setStyleSheet = QtGui.QWidget.setStyleSheet
        original_QWidget_resize = QtGui.QWidget.resize
        original_QWidget_move = QtGui.QWidget.move

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
                    args = [
                        min(args[0]*2, 16777215),
                        min(args[1]*2, 16777215),
                    ]

                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"  override resize {args=}")

                return original_QWidget_resize(self, *args, **kwargs)

            def move(self, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQWidget::move {args=}")
                if len(args) == 2 and isinstance(args[0], int) and isinstance(args[1], int):
                    args = [
                        min(args[0]*2, 16777215),
                        min(args[1]*2, 16777215),
                    ]

                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"  override move {args=}")

                return original_QWidget_move(self, *args, **kwargs)

            def setContentsMargins(self, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQWidget::setContentsMargins {args=}")
                if len(args) == 4 and isinstance(args[0], int) and isinstance(args[1], int) and isinstance(args[2], int) and isinstance(args[3], int):
                    args = [args[0]*2, args[1]*2, args[2]*2, args[3]*2]
                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"  override {args=}")

                return original_QWidget_setContentsMargins(self, *args, **kwargs)

        #QtGui.QWidget.setContentsMargins = MyQWidget.setContentsMargins
        QtGui.QWidget.styleSheet = MyQWidget.styleSheet
        QtGui.QWidget.setStyleSheet = MyQWidget.setStyleSheet
        QtGui.QWidget.resize = MyQWidget.resize
        QtGui.QWidget.move = MyQWidget.move


    @classmethod
    def _patch_QLayout(cls, QtGui):
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

        # QtGui.QLayout.setContentsMargins = MyQLayout.setContentsMargins
        # QtGui.QLayout.setSpacing = MyQLayout.setSpacing
        # QtGui.QLayout.spacing = MyQLayout.spacing

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
                    args = [
                        min(args[0] * 2, 16777215),
                        min(args[1] * 2, 16777215),
                    ]

                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"   override {args=}")

                original_QSize.__init__(self, *args)

        QtCore.QSize = MyQSize

    @classmethod
    def _patch_QPoint(cls, QtCore):
        original_QPoint = QtCore.QPoint

        class MyQPoint(original_QPoint):
            def __init__(self, *args):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQPoint {args=}")

                if len(args) == 2 and isinstance(args[0], int) and isinstance(args[1], int):
                    args = [
                        min(args[0] * 2, 16777215),
                        min(args[1] * 2, 16777215),
                    ]

                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"   override {args=}")

                original_QPoint.__init__(self, *args)

        QtCore.QPoint = MyQPoint

    @classmethod
    def _patch_QRect(cls, QtCore):
        original_QRect = QtCore.QRect

        class MyQRect(original_QRect):
            def __init__(self, *args):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQRect {args=}")

                if len(args) == 4 and isinstance(args[0], int) and isinstance(args[1], int)  and isinstance(args[2], int)  and isinstance(args[3], int):
                    args = [
                        min(args[0] * 2, 16777215),
                        min(args[1] * 2, 16777215),
                        min(args[2] * 2, 16777215),
                        min(args[3] * 2, 16777215),
                    ]

                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"   override {args=}")

                original_QRect.__init__(self, *args)

        QtCore.QRect = MyQRect


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


