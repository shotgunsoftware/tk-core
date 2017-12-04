# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
QT Login dialog for authenticating to a Shotgun server.

--------------------------------------------------------------------------------
NOTE! This module is part of the authentication library internals and should
not be called directly. Interfaces and implementation of this module may change
at any point.
--------------------------------------------------------------------------------
"""


from .qt_abstraction import QtGui


class RecentBox(QtGui.QComboBox):

    def __init__(self, parent):
        super(RecentBox, self).__init__(parent)

        self.setEditable(True)

        self._recent_items_model = QtGui.QStringListModel(self)

        self._drop_down_model = QtGui.QSortFilterProxyModel(self)
        self._drop_down_model.setSourceModel(self._recent_items_model)
        self.setModel(self._drop_down_model)

        self._filter_model = QtGui.QSortFilterProxyModel(self)
        self._filter_model.setSourceModel(self._drop_down_model)

        self._completer = QtGui.QCompleter()
        self._completer.setCompletionMode(QtGui.QCompleter.UnfilteredPopupCompletion)
        self._completer.setModel(self._filter_model)

        self.setCompleter(self._completer)

        self.lineEdit().textEdited.connect(self._current_text_changed)

    def set_style_sheet(self, style_sheet):
        self.completer().popup().setStyleSheet(style_sheet)

    def set_recent_items(self, items):
        self._recent_items_model.setStringList(items)

    def set_selection(self, item):
        for idx in range(self._drop_down_model.rowCount()):
            if self._drop_down_model.data(self._drop_down_model.index(idx, 0)) == item:
                self.setCurrentIndex(idx)
                break

    def _current_text_changed(self, text):
        self._filter_model.setFilterFixedString(text)
        self._filter_model.invalidate()
