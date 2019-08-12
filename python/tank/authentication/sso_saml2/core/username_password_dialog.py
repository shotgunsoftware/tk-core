# Copyright (c) 2017 Autodesk.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.
"""
Module to support Web login via a web browser and automated session renewal.
"""

from __future__ import print_function

# pylint: disable=import-error
try:
    from .ui.qt_abstraction import QtGui

    class UsernamePasswordDialog(QtGui.QDialog):
        """Simple dialog to request a username and password from the user."""

        def __init__(self):
            super(UsernamePasswordDialog, self).__init__()

            # For now we fix the GUI size.
            self.setWindowTitle("Authentication Required")
            self.setMinimumWidth(420)
            self.setMinimumHeight(120)

            # set up the layout
            form_grid_layout = QtGui.QGridLayout(self)

            # initialize the username combo box so that it is editable
            self._edit_username = QtGui.QLineEdit(self)

            # initialize the password field so that it does not echo characters
            self._edit_password = QtGui.QLineEdit(self)
            self._edit_password.setEchoMode(QtGui.QLineEdit.Password)

            # initialize the labels
            label_username = QtGui.QLabel(self)
            label_password = QtGui.QLabel(self)
            label_username.setText("Username:")
            label_password.setText("Password:")

            # initialize buttons
            buttons = QtGui.QDialogButtonBox(self)
            buttons.addButton(QtGui.QDialogButtonBox.Ok)
            buttons.addButton(QtGui.QDialogButtonBox.Cancel)
            buttons.button(QtGui.QDialogButtonBox.Ok).setText("Login")
            buttons.button(QtGui.QDialogButtonBox.Cancel).setText("Cancel")

            # place components into the dialog
            form_grid_layout.addWidget(label_username, 0, 0)
            form_grid_layout.addWidget(self._edit_username, 0, 1)
            form_grid_layout.addWidget(label_password, 1, 0)
            form_grid_layout.addWidget(self._edit_password, 1, 1)
            form_grid_layout.setRowStretch(2, 1)
            form_grid_layout.addWidget(buttons, 3, 1)

            self.setLayout(form_grid_layout)

            buttons.button(QtGui.QDialogButtonBox.Ok).clicked.connect(self._on_enter_credentials)
            buttons.button(QtGui.QDialogButtonBox.Cancel).clicked.connect(self.close)

        @property
        def username(self):
            """Getter for username."""
            return self._edit_username.text()

        @username.setter
        def username(self, username):
            """Setter for username."""
            self._edit_username.setText(username)

        @property
        def password(self):
            """Getter for password."""
            return self._edit_password.text()

        @password.setter
        def password(self, password):
            """Setter for password."""
            self._edit_password.setText(password)

        def _on_enter_credentials(self):
            """Callback when clicking Ok."""
            if self._edit_username.text() == "":
                self._edit_username.setFocus()
                return

            if self._edit_password.text() == "":
                self._edit_password.setFocus()
                return

            self.accept()
except ImportError:
    class UsernamePasswordDialog(object):
        """Minimalistic implementation."""
        def __init__(self):
            self._username = ""
            self._password = ""

        @property
        def username(self):
            """Getter for username."""
            return self._username

        @username.setter
        def username(self, username):
            """Setter for username."""
            self._username = username

        @property
        def password(self):
            """Getter for password."""
            return self._password

        @password.setter
        def password(self, password):
            """Setter for password."""
            self._password = password

        def show(self):
            """Stub implementation"""
            pass

        def raise_(self):
            """Stub implementation"""
            pass

        # pylint: disable=no-self-use
        def exec_(self):
            """Stub implementation"""
            return 1


def main():
    """Simple test"""
    _ = QtGui.QApplication([])
    login_dialog = UsernamePasswordDialog()
    login_dialog.username = "TheUsername"
    login_dialog.password = "ThePassword"
    login_dialog.show()
    login_dialog.raise_()
    if login_dialog.exec_():
        print("Username: %s" % login_dialog.username)
        print("Password: %s" % login_dialog.password)
    else:
        print("Canceled the operation")


if __name__ == "__main__":
    main()
