# Copyright (c) 2017 Shotgun Software Inc.
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

import re

from PySide import QtCore
from .qt_abstraction import QtGui
from .qt5_like_line_edit import Qt5LikeLineEdit


class FuzzyMatcher():
    """
    Implement an algorithm to rank strings via fuzzy matching.

    Based on the analysis at
    http://crossplatform.net/sublime-text-ctrl-p-fuzzy-matching-in-python
    """
    def __init__(self, pattern, case_sensitive=False):
        # construct a pattern that matches the letters in order
        # for example "aad" turns into "(a).*?(a).*?(d)".
        self.pattern = ".*?".join("(%s)" % re.escape(char) for char in pattern)
        if case_sensitive:
            self.re = re.compile(self.pattern)
        else:
            self.re = re.compile(self.pattern, re.IGNORECASE)

    def score(self, string, highlighter=None):
        match = self.re.search(string)
        if match is None:
            # letters did not appear in order
            return (0, string)
        else:
            # have a match, scores are higher for matches near the beginning
            # or that are clustered together
            score = 100.0 / ((1 + match.start()) * (match.end() - match.start() + 1))

            if highlighter is not None:
                highlighted = string[0:match.start(1)]
                for group in xrange(1, match.lastindex + 1):
                    if group == match.lastindex:
                        remainder = string[match.end(group):]
                    else:
                        remainder = string[match.end(group):match.start(group + 1)]
                    highlighted += highlighter(match.group(group)) + remainder
            else:
                highlighted = string
            return (score, highlighted)


COMPLETER_PROXY_DISPLAY_ROLE = 2048


class CompletionFilterProxy(QtGui.QSortFilterProxyModel):

    def __init__(self, parent):
        super(CompletionFilterProxy, self).__init__(parent)
        self.set_filter("")

    def set_filter(self, text):
        self._fuzzy_matcher = FuzzyMatcher(text, case_sensitive=False) if len(text) > 0 else None
        self.invalidateFilter()
        self.sort(0)
        self.layoutChanged.emit()

    def filterAcceptsRow(self, row, source_parent):
        if not self._fuzzy_matcher:
            return True
        else:
            index = self.sourceModel().index(row, 0, source_parent)
            result = self._fuzzy_matcher.score(self.sourceModel().data(index))
            return result[0]

    def data(self, index, role):
        """
        """
        # Retrieve the data, but filter it if we want to display it so search results have some
        # highlighting.
        text = super(CompletionFilterProxy, self).data(index, role)
        if role == QtCore.Qt.DisplayRole and self._fuzzy_matcher:
            return self._fuzzy_matcher.score(text)[1]
        else:
            return text

    def lessThan(self, left, right):
        """
        Sorts items based on their fuzzy-matching score. Higher scores show up first.
        """
        # If there is no filter, consider both entries to be of the same score.
        if self._fuzzy_matcher:
            left_score = self._fuzzy_matcher.score(left.data())
            right_score = self._fuzzy_matcher.score(right.data())
        else:
            left_score = 0
            right_score = 0

        if left_score != right_score:
            # The higher the score, the earlier the result should be in the list.
            return left_score > right_score
        else:
            # Score is the same, so sort alphabetically
            return left.data() < right.data()


class RecentBox(QtGui.QComboBox):
    """
    Combo box specialisation that handles all the filtering, sorting and auto-completion
    for a list of recent items. Items are sorted alphabetically so they can be found easily
    in the UI.
    """

    def __init__(self, parent):
        super(RecentBox, self).__init__(parent)

        self.setEditable(True)

        # Using Qt5LikeLineEdit so we have a placeholder even when the line edit is selected.
        self.setLineEdit(Qt5LikeLineEdit(self))

        # Create a model sorted alphabetically for the recent items.
        self._recent_items_model = QtGui.QStringListModel(self)
        self._drop_down_model = QtGui.QSortFilterProxyModel(self)
        self._drop_down_model.setSourceModel(self._recent_items_model)
        self.setModel(self._drop_down_model)

        # We'll use a completer that shows all results and we'll do the matching ourselves, as the completion
        # engine can only work from the beginning of a string...
        self._completer = QtGui.QCompleter()
        self._completer.setCompletionMode(QtGui.QCompleter.UnfilteredPopupCompletion)

        # We'll do our own filtering.
        self._filter_model = CompletionFilterProxy(self)
        self._filter_model.setSourceModel(self._drop_down_model)
        self._completer.setModel(self._filter_model)
        self.setCompleter(self._completer)

        # Each time the user types something, we'll update the filter.
        self.lineEdit().textEdited.connect(self._current_text_changed)

    def set_style_sheet(self, style_sheet):
        """
        Allows to the the completer's pop-up widget style sheet.

        :param str style_sheet: Style sheet for the completer's pop-up widget.
        """
        self.completer().popup().setStyleSheet(style_sheet)

    def set_recent_items(self, items):
        """
        Sets the list of recent items.

        :param list(str): List of strings to display.
        """
        self._recent_items_model.setStringList(items)

    def set_selection(self, item):
        """
        Sets the currently selected item in the drop down.

        :param str item: String to select in the recent box.
        """
        for idx in range(self._drop_down_model.rowCount()):
            if self._drop_down_model.data(self._drop_down_model.index(idx, 0)) == item:
                self.setCurrentIndex(idx)
                break

    def _current_text_changed(self, text):
        """
        Updates the filter each time the user types something.

        :param str text: Text the user has just typed in.
        """
        self._filter_model.set_filter(text)

    def set_placeholder_text(self, text):
        """
        Sets the placeholder text to display in the combo box's line edit.
        """
        # Older versions of Qt don't support this method.
        if hasattr(self.lineEdit(), "setPlaceholderText"):
            self.lineEdit().setPlaceholderText(text)
