# Copyright (c) 2025 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.


class PySide2asPySide6Patcher:
    @staticmethod
    def _patch_QtWebEngineCore(qt_webengine_core, classes):
        for cls in classes:
            setattr(qt_webengine_core, cls.__name__, cls)
        return qt_webengine_core

    @staticmethod
    def _patch_QtGui(qt_gui, classes):
        for cls in classes:
            setattr(qt_gui, cls.__name__, cls)
        return qt_gui
