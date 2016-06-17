# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Imports Qt without having to worry whether we are using PyQt4 or PySide.
"""
try:
    from PySide2 import QtCore, QtWidgets, QtGui
    # FIXME:  We need to refactor the PySide2 patching code from sgtk.platform.qt. This will get
    # us going in the meantime.

    class _ModuleHack(object):
        """
        Merges the QtGui, QtCore and QtWidgets together so we don't have to tailor code
        for the authentication module for differences between Qt4 and Qt5 class layout.
        """

        def __init__(self, core, gui, widgets):
            """
            Constructor.
            """
            self._core = core
            self._gui = gui
            self._widgets = widgets
            widgets.QApplication.UnicodeUTF8 = 1

        def __getattr__(self, name):
            """
            Looks in every Qt module for the requested class.
            """
            if hasattr(self._core, name):
                return getattr(self._core, name)
            if hasattr(self._gui, name):
                return getattr(self._gui, name)
            if hasattr(self._widgets, name):
                return getattr(self._widgets, name)
            return None

    hack = _ModuleHack(QtCore, QtGui, QtWidgets)
    QtCore = hack
    QtGui = hack
except:
    try:
        from PySide import QtCore, QtGui
    except ImportError:
        try:
            from PyQt4 import QtCore, QtGui
        except:
            pass
