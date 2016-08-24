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
Qt5-like QLineEdit
"""


from .qt_abstraction import QtGui, QtCore, qt_version_tuple


# If we're on Qt4, we want the placeholder in the login dialog.
if qt_version_tuple[0] == 4:
    class Qt5LikeLineEdit(QtGui.QLineEdit):
        """
        QLineEdit that shows a placeholder in an empty editor, even if the widget is focused.
        """

        # Constants taken from
        # http://code.metager.de/source/xref/lib/qt/src/gui/widgets/qlineedit_p.cpp#59
        _horizontal_margin = 2
        _vertical_margin = 1

        def paintEvent(self, paint_event):
            """
            Paints the line editor and adds a placeholder on top when the string is empty, even if focused.
            """
            # Draws the widget. If the widget is out of focus, it will draw the placeholder.
            QtGui.QLineEdit.paintEvent(self, paint_event)

            # This code is based on the C++ implementation of the paint event.
            # http://code.metager.de/source/xref/lib/qt/src/gui/widgets/qlineedit.cpp#1889
            #
            # The translated code keeps the flow and the naming as close as possible to the original
            # in order to easily map one section and variable to another, unless preserving such
            # consistency actually made the code harder to read.

            # If the box is empty and focused, draw the placeholder
            if self.hasFocus() and not self.text() and self.placeholderText():

                p = QtGui.QPainter(self)
                pal = self.palette()

                panel = QtGui.QStyleOptionFrameV2()
                self.initStyleOption(panel)
                r = self.style().subElementRect(QtGui.QStyle.SE_LineEditContents, panel, self)

                text_margins = self.textMargins()

                # self.textMargins() retrieves the same values as d->rightTextMargin, ... in the C++ code.
                r.setX(r.x() + text_margins.left())
                r.setY(r.y() + text_margins.top())
                r.setRight(r.right() - text_margins.right())
                r.setBottom(r.bottom() - text_margins.bottom())
                p.setClipRect(r)

                fm = self.fontMetrics()

                visual_alignment = QtGui.QStyle.visualAlignment(self.layoutDirection(), QtCore.Qt.AlignLeft)
                vertical_alignment = visual_alignment & QtCore.Qt.AlignVertical_Mask

                if vertical_alignment == QtCore.Qt.AlignBottom:
                    vscroll = r.y() + r.height() - fm.height() - self._vertical_margin
                elif vertical_alignment == QtCore.Qt.AlignTop:
                    vscroll = r.y() + self._vertical_margin
                else:
                    vscroll = r.y() + (r.height() - fm.height() + 1) / 2

                line_rect = QtCore.QRect(
                    r.x() + self._horizontal_margin,
                    vscroll,
                    r.width() - 2 * self._horizontal_margin,
                    fm.height()
                )

                min_left_bearing = max(0, -fm.minLeftBearing())

                col = pal.text().color()
                col.setAlpha(128)
                oldpen = p.pen()
                p.setPen(col)
                line_rect.adjust(min_left_bearing, 0, 0, 0)

                elided_text = fm.elidedText(self.placeholderText(), QtCore.Qt.ElideRight, line_rect.width())
                p.drawText(line_rect, vertical_alignment, elided_text)
                p.setPen(oldpen)
else:
    # Qt5 always has the placeholder.
    Qt5LikeLineEdit = QtGui.QLineEdit
