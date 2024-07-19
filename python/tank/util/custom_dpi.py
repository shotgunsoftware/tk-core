# Copyright (c) 2024 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import re

## TODO: do the same with:
# setSpacing
# setMargin
# setStretch / setHorizontalStretch / setVerticalStretch ??
# addSpacing(size)
# addStretch([stretch=0])

QWIDGETSIZE_MAX = 16777215


ENABLED = True


class DPIQtPatcher(object):
    def __init__(self, dpi_factor, qtCore, qtGui):
        print(f"DPIQtPatcher::__init__")

        self.dpi_factor = dpi_factor
        self.qtCore = qtCore
        self.qtGui = qtGui

        self.re_css = re.compile("([0-9]+)\\s?(px)")


    def process(self):
        print(f"DPIQtPatcher::process")

        if hasattr(self.qtCore, "__custom_dpi_patch_applied"):
            print(f"  patch already applied on module")
            return

        self._patch_QWidget()

        self._patch_QLayout()
        self._patch_QHBoxLayout()
        self._patch_QSpacerItem()

        # self._patch_QLabel()
        self._patch_QSize()
        #self._patch_QPoint()
        self._patch_QRect()

        self.qtCore.__custom_dpi_patch_applied = True


    def apply_dpi_factor(self, value):
        return min(value * self.dpi_factor, QWIDGETSIZE_MAX)


    def css_re_callback(self, matchobj):
        v = int(matchobj.group(1))
        return f"{self.apply_dpi_factor(v)}px"


    def _patch_QWidget(self):
        original_QWidget_setContentsMargins = self.qtGui.QWidget.setContentsMargins
        original_QWidget_setStyleSheet = self.qtGui.QWidget.setStyleSheet
        original_QWidget_resize = self.qtGui.QWidget.resize
        original_QWidget_move = self.qtGui.QWidget.move

        class MyQWidget:
            def styleSheet(instance, *args, **kwargs):
                return getattr(instance, "orig_stylesheet_content", "")

            def setStyleSheet(instance, *args, **kwargs):
                if not ENABLED:
                    pass
                elif len(args) == 1 and isinstance(args[0], str):
                    instance.orig_stylesheet_content = args[0]

                    if "GLOBAL_DEBUG" in os.environ:
                        print("MyQWidget::setStyleSheet")
                        print(instance.orig_stylesheet_content)

                    args = [self.re_css.sub(self.css_re_callback, args[0])]

                    if "GLOBAL_DEBUG" in os.environ:
                        print("  override css")
                        print(args[0])
                        print()

                return original_QWidget_setStyleSheet(instance, *args, **kwargs)

            def resize(instance, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQWidget::resize {args=}")

                if not ENABLED:
                    pass
                elif len(args) == 2 and isinstance(args[0], int) and isinstance(args[1], int):
                    args = [
                        self.apply_dpi_factor(args[0]),
                        self.apply_dpi_factor(args[1]),
                    ]

                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"  override resize {args=}")

                return original_QWidget_resize(instance, *args, **kwargs)

            def move(instance, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQWidget::move {args=}")

                if not ENABLED:
                    pass
                elif len(args) == 2 and isinstance(args[0], int) and isinstance(args[1], int):
                    args = [
                        self.apply_dpi_factor(args[0]),
                        self.apply_dpi_factor(args[1]),
                    ]

                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"  override move {args=}")

                return original_QWidget_move(instance, *args, **kwargs)

            def setContentsMargins(instance, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQWidget::setContentsMargins {args=}")

                if not ENABLED:
                    pass
                elif len(args) == 4 and isinstance(args[0], int) and isinstance(args[1], int) and isinstance(args[2], int) and isinstance(args[3], int):
                    args = [
                        self.apply_dpi_factor(args[0]),
                        self.apply_dpi_factor(args[1]),
                        self.apply_dpi_factor(args[2]),
                        self.apply_dpi_factor(args[3]),
                    ]

                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"  override {args=}")

                return original_QWidget_setContentsMargins(instance, *args, **kwargs)

        self.qtGui.QWidget.setContentsMargins = MyQWidget.setContentsMargins
        self.qtGui.QWidget.styleSheet = MyQWidget.styleSheet
        self.qtGui.QWidget.setStyleSheet = MyQWidget.setStyleSheet
        self.qtGui.QWidget.resize = MyQWidget.resize
        #self.qtGui.QWidget.move = MyQWidget.move


    def _patch_QLayout(self):
        original_QLayout_setContentsMargins = self.qtGui.QLayout.setContentsMargins
        original_QLayout_setSpacing = self.qtGui.QLayout.setSpacing
        original_QLayout_spacing = self.qtGui.QLayout.spacing

        class MyQLayout:
            def setContentsMargins(instance, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQLayout::setContentsMargins {args=}")

                if not ENABLED:
                    pass
                elif len(args) == 4 and isinstance(args[0], int) and isinstance(args[1], int) and isinstance(args[2], int) and isinstance(args[3], int):
                    args = [
                        self.apply_dpi_factor(args[0]),
                        self.apply_dpi_factor(args[1]),
                        self.apply_dpi_factor(args[2]),
                        self.apply_dpi_factor(args[3]),
                    ]

                    if "GLOBAL_DEBUG" in os.environ:
                       print(f"  override {args=}")

                return original_QLayout_setContentsMargins(instance, *args, **kwargs)

            def setSpacing(instance, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print("MyQLayout::setSpacing")

                if not ENABLED:
                    pass
                elif len(args) and isinstance(args[0], int):
                    instance.orig_spacing_content = args[0]

                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"  override {args=}")

                    args = [self.apply_dpi_factor(args[0]), *args[1:]]

                return original_QLayout_setSpacing(instance, *args, **kwargs)

            def spacing(instance, *args, **kwargs):
                if not ENABLED:
                    pass
                elif hasattr(instance, "orig_spacing_content"):
                    return instance.orig_spacing_content
            
                return original_QLayout_spacing(instance, *args, **kwargs)

        self.qtGui.QLayout.setContentsMargins = MyQLayout.setContentsMargins
        self.qtGui.QLayout.setSpacing = MyQLayout.setSpacing
        self.qtGui.QLayout.spacing = MyQLayout.spacing


    def _patch_QHBoxLayout(self):
        original_QHBoxLayout = self.qtGui.QHBoxLayout

        class MyQHBoxLayout(original_QHBoxLayout):
            def setSpacing(instance, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print()
                    print(f"MyQHBoxLayout::setSpacing {args=}")
                if len(args) and isinstance(args[0], int):
                    args = [self.apply_dpi_factor(args[0]), *args[1:]]
                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"  override {args=}")

                return original_QHBoxLayout.setSpacing(instance, *args, **kwargs)

            def spacing(instance, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQHBoxLayout::spacing {args=}")
                return original_QHBoxLayout.spacing(instance, *args, **kwargs)

        self.qtGui.QHBoxLayout = MyQHBoxLayout


    def _patch_QSpacerItem(self):
        original_QSpacerItem = self.qtGui.QSpacerItem

        class MyQSpacerItem(original_QSpacerItem):
            def __init__(instance, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print()
                    print(f"MyQSpacerItem {args=}")

                if not ENABLED:
                    pass
                elif len(args) > 2 and isinstance(args[0], int) and isinstance(args[1], int):
                    args = [
                        self.apply_dpi_factor(args[0]),
                        self.apply_dpi_factor(args[1]),
                        *args[2:]
                    ]

                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"  override {args=}")

                original_QSpacerItem.__init__(instance, *args, **kwargs)

            def changeSize(instance, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQSpacerItem::changeSize {args=}")

                if not ENABLED:
                    pass
                elif len(args) > 2 and isinstance(args[0], int) and isinstance(args[1], int):
                    args = [
                        self.apply_dpi_factor(args[0]),
                        self.apply_dpi_factor(args[1]),
                        *args[2:]
                    ]

                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"  override {args=}")

                original_QSpacerItem.changeSize(instance, *args, **kwargs)

        self.qtGui.QSpacerItem = MyQSpacerItem


    def _patch_QLabel(self):
        original_QLabel = self.qtGui.QLabel

        class MyQLabel(original_QLabel):
            def setMargin(instance, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQLabel::setMargin {args=}")

                if not ENABLED:
                    pass
                elif len(args) and isinstance(args[0], int):
                    args = [self.apply_dpi_factor(args[0]), *args[1:]]
                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"  override {args=}")

                return original_QLabel.setMargin(instance, *args, **kwargs)

        self.qtGui.QLabel = MyQLabel


    def _patch_QSize(self):
        original_QSize = self.qtCore.QSize

        class MyQSize(original_QSize):
            def __init__(instance, *args):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQSize {args=}")

                if not ENABLED:
                    pass
                elif len(args) == 2 and isinstance(args[0], int) and isinstance(args[1], int):
                    args = [
                        self.apply_dpi_factor(args[0]),
                        self.apply_dpi_factor(args[1]),
                    ]

                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"   override {args=}")

                original_QSize.__init__(instance, *args)

        self.qtCore.QSize = MyQSize


    def _patch_QPoint(self):
        original_QPoint = self.qtCore.QPoint

        class MyQPoint(original_QPoint):
            def __init__(instance, *args):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQPoint {args=}")

                if not ENABLED:
                    pass
                elif len(args) == 2 and isinstance(args[0], int) and isinstance(args[1], int):
                    args = [
                        self.apply_dpi_factor(args[0]),
                        self.apply_dpi_factor(args[1]),
                    ]

                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"   override {args=}")

                original_QPoint.__init__(instance, *args)

        self.qtCore.QPoint = MyQPoint


    def _patch_QRect(self):
        original_QRect = self.qtCore.QRect

        class MyQRect(original_QRect):
            def __init__(instance, *args):
                if "GLOBAL_DEBUG" in os.environ:
                    print(f"MyQRect {args=}")

                if not ENABLED:
                    pass
                elif len(args) == 4 and isinstance(args[0], int) and isinstance(args[1], int)  and isinstance(args[2], int)  and isinstance(args[3], int):
                    args = [
                        self.apply_dpi_factor(args[0]),
                        self.apply_dpi_factor(args[1]),
                        self.apply_dpi_factor(args[2]),
                        self.apply_dpi_factor(args[3]),
                    ]

                    if "GLOBAL_DEBUG" in os.environ:
                        print(f"   override {args=}")

                original_QRect.__init__(instance, *args)

        self.qtCore.QRect = MyQRect


    def _patch_QPixmap(self):
        original_QPixmap_init = self.qtGui.QPixmap.__init__
        class MyQPixmap:
            def __init__(instance, *args, **kwargs):
                if "GLOBAL_DEBUG" in os.environ:
                    print("MyQPixmap.__init__", args,  kwargs)

                return original_QPixmap_init(instance, *args, **kwargs)

        self.qtGui.QPixmap.__init__ = MyQPixmap.__init__
