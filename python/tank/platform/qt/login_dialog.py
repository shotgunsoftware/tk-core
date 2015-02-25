# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

# It is possible not to have an engine running yet so try to import different flavors of Qt.
try:
    from . import QtCore, QtGui
except ImportError:
    try:
        from PySide import QtCore, QtGui
    except ImportError:
            from PyQt4 import QtCore, QtGui

from tank.errors import TankAuthenticationError

from . import resources_rc
from . import ui_login_dialog
from tank.util import authentication


class LoginDialog(QtGui.QDialog):
    """
    Dialog for getting user crendentials.
    """
    def __init__(self, title, session_renewal, hostname="", login="", http_proxy=None, pixmap=None, stay_on_top=True, parent=None):
        """
        Constructs a dialog.

        :param title: Title of this dialog.
        :param session_renewal: Configures the dialog for session renewal or user login.
        :param hostname: The string to populate the site field with. Defaults to "".
        :param login: The string to populate the login field with. Defaults to "".
        :param http_proxy: The proxy server to use when testing authentication. Defaults to None.
        :param pixmap: QPixmap to show in the dialog (defaults to the Shotgun logo)
        :param stay_on_top: Whether the dialog should stay on top (defaults to True)
        :param parent: The Qt parent for the dialog (defaults to None)
        """
        QtGui.QDialog.__init__(self, parent)

        # set the dialog to always stay on top
        if stay_on_top:
            self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

        # setup the gui
        self.ui = ui_login_dialog.Ui_LoginDialog()
        self.ui.setupUi(self)

        # Set the title
        self.setWindowTitle(title)

        # Assign credentials
        self._http_proxy = http_proxy
        self.ui.site.setText(hostname)
        self.ui.login.setText(login)

        # default focus
        if self.ui.site.text():
            if self.ui.login.text():
                self.ui.password.setFocus()
            else:
                self.ui.login.setFocus()
        else:
            self.ui.site.setFocus()

        # set the logo
        if not pixmap:
            pixmap = QtGui.QPixmap(":/Tank.Platform.Qt/shotgun_logo_light_medium.png")
        self.ui.logo.setPixmap(pixmap)

        # Disable keyboard input in the site and login boxes if we are simply renewing the session.
        self.ui.site.setReadOnly(session_renewal)
        self.ui.login.setReadOnly(session_renewal)

        if session_renewal:
            self._set_error_message("Your session has expired. Please enter your Shotgun password.")
        else:
            self._set_message("Please enter your Shotgun credentials.")

        # hook up signals
        self.connect(self.ui.sign_in, QtCore.SIGNAL("clicked()"), self._ok_pressed)
        self.connect(self.ui.cancel, QtCore.SIGNAL("clicked()"), self._cancel_pressed)

    def _set_message(self, message):
        """
        Set the message in the dialog.
        :param message: Message to display in the dialog.
        """
        if not message:
            self.ui.message.hide()
        else:
            self.ui.message.setText(message)
            self.ui.message.show()

    def _cancel_pressed(self):
        """
        Invoked when the user clicks cancel in the ui.
        """
        self.reject()

    def result(self):
        """
        Displays a modal dialog asking for the credentials.
        :returns: A tuple of (hostname, username and session token) string if the user authenticated
                  None if the user cancelled.
        """
        self.exec_()
        if QtGui.QDialog.result(self) == QtGui.QDialog.Accepted:
            return (self.ui.site.text().encode("utf-8"),
                    self.ui.login.text().encode("utf-8"),
                    self._new_session_token)
        else:
            return None

    def _set_error_message(self, message):
        """
        Set the error message in the dialog.
        :param message: Message to display in red in the dialog.
        """
        self.ui.message.setText("<font style='color: rgb(252, 98, 70);'>%s</font>" % message)

    def _ok_pressed(self):
        """
        validate the values, accepting if login is successful and display an error message if not.
        """
        # pull values from the gui
        site = self.ui.site.text()
        login = self.ui.login.text()
        password = self.ui.password.text()

        if len(site) == 0:
            self._set_error_message("Please enter the address of the site to connect to.")
            return
        if len(login) == 0:
            self._set_error_message("Please enter your login name.")
            return
        if len(password) == 0:
            self._set_error_message("Please enter your password.")
            return

        # if not protocol specified assume https
        if len(site.split("://")) == 1:
            site = "https://%s" % site
            self.ui.site.setText(site)

        try:
            # set the wait cursor
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            QtGui.QApplication.processEvents()

            # try and authenticate
            self._new_session_token = authentication.generate_session_token(
                site, login, password, self._http_proxy
            )
        except TankAuthenticationError, e:
            # authentication did not succeed
            self._set_error_message(e[0])
            self.ui.message.show()
            return
        finally:
            # restore the cursor
            QtGui.QApplication.restoreOverrideCursor()
            QtGui.QApplication.processEvents()        # dialog is done
        self.accept()
