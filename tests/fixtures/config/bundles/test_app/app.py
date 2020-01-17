# Copyright (c) 2019 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
A simple app to support unit tests.
"""

from tank.platform import Application


class TestApp(Application):
    """
    Test app with a single action that displays a dialog with a button
    that closes the window.

    You can close the dialog by doing
    ``engine.apps["test_app"].dismiss_button.click()``
    """

    def init_app(self):
        self.dismiss_button = None
        if not self.engine.has_ui:
            return

        self.engine.register_command("test_app", self._show_app)

    def _show_app(self):
        """
        Shows an app with a button in it.
        """
        from sgtk.platform.qt import QtGui

        class AppDialog(QtGui.QWidget):
            def __init__(self, parent=None):
                super(AppDialog, self).__init__(parent)
                self._layout = QtGui.QVBoxLayout(self)
                self.button = QtGui.QPushButton("Close", parent=self)
                self.button.clicked.connect(self.close)
                self._layout.addWidget(self.button)

        widget = self.engine.show_dialog("Simple Test App", self, AppDialog)
        self.dismiss_button = widget.button
