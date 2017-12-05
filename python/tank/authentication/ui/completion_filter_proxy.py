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

import re

from .qt_abstraction import QtGui


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


class CompletionFilterProxy(QtGui.QSortFilterProxyModel):

    def __init__(self, parent):
        super(CompletionFilterProxy, self).__init__(parent)
        self.set_filter("")

    def set_filter(self, text):
        self._fuzzy_matcher = FuzzyMatcher(text, case_sensitive=False)
        self.invalidateFilter()
        self.sort(0)
        self.layoutChanged.emit()

    def filterAcceptsRow(self, row, source_parent):
        index = self.sourceModel().index(row, 0, source_parent)
        return self._fuzzy_matcher.score(self.sourceModel().data(index), highlighter=None)[0] > 0

    def lessThan(self, left, right):
        left_data = self.sourceModel().data(left)
        right_data = self.sourceModel().data(right)

        return self._less_than(left_data, right_data)

    def _less_than(self, left_data, right_data):
        left_score = self._fuzzy_matcher.score(left_data)
        right_score = self._fuzzy_matcher.score(right_data)

        if left_score != right_score:
            # The higher the score, the earlier the result should be in the list.
            return left_score > right_score
        else:
            # Score is the same, so sort alphabetically
            return left_data < right_data
