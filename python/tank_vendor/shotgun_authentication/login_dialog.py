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
Login dialog for authenticating to a Shotgun server.
"""

from .ui import resources_rc
from .ui import login_dialog
from . import session_cache
from .errors import AuthenticationError
from .ui.qt_abstraction import QtGui, QtCore


class LoginDialog(QtGui.QDialog):
    """
    Dialog for getting user crendentials.
    """
    def __init__(self, is_session_renewal, hostname="", login="", fixed_host=False, http_proxy=None, parent=None):
        """
        Constructs a dialog.

        :param is_session_renewal: Boolean indicating if we are renewing a session or authenticating a user from scratch.
        :param hostname: The string to populate the site field with. Defaults to "".
        :param login: The string to populate the login field with. Defaults to "".
        :param fixed_host: Indicates if the hostname can be changed. Defaults to False.
        :param http_proxy: The proxy server to use when testing authentication. Defaults to None.
        :param parent: The Qt parent for the dialog (defaults to None)
        """
        QtGui.QDialog.__init__(self, parent)

        # setup the gui
        self.ui = login_dialog.Ui_LoginDialog()
        self.ui.setupUi(self)

        # Set the title
        self.setWindowTitle("Shotgun Login")

        # Assign credentials
        self._http_proxy = http_proxy
        self.ui.site.setText(hostname)
        self.ui.login.setText(login)

        # default focus
        if self.ui.site.text():
            if self.ui.login.text():
                self.ui.password.setFocus(QtCore.Qt.OtherFocusReason)
            else:
                self.ui.login.setFocus(QtCore.Qt.OtherFocusReason)
        else:
            self.ui.site.setFocus(QtCore.Qt.OtherFocusReason)

        # set the logo
        self.ui.logo.setPixmap(QtGui.QPixmap(":/shotgun_authentication/shotgun_logo_light_medium.png"))

        if fixed_host:
            self._disable_widget(
                self.ui.site,
                "You can't edit the host, your core is configured for this site."
            )

        # Disable keyboard input in the site and login boxes if we are simply renewing the session.
        # If the host is fixed, disable the site textbox.
        if is_session_renewal:
            self._disable_widget(
                self.ui.site,
                "You are renewing your session: you can't change your host.")
            self._disable_widget(
                self.ui.login,
                "You are renewing your session: you can't change your login."
            )

        if is_session_renewal:
            self._set_message("Your session has expired. Please enter your password.")
        else:
            self._set_message("Please enter your credentials.")

        # hook up signals
        self.ui.sign_in.clicked.connect(self._ok_pressed)
        self.ui.cancel.clicked.connect(self.reject)

    def _disable_widget(self, widget, tooltip_text):
        widget.setReadOnly(True)
        widget.setEnabled(False)
        widget.setToolTip(tooltip_text)

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

    def show(self):
        """
        Shows the ui.
        """
        QtGui.QDialog.show(self)
        self.activateWindow()
        self.raise_()

    def exec_(self):
        """
        Displays the window modally.
        """
        self.activateWindow()
        self.raise_()
        # the trick of activating + raising does not seem to be enough for
        # modal dialogs. So force put them on top as well.
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | self.windowFlags())
        return QtGui.QDialog.exec_(self)

    def result(self):
        """
        Displays a modal dialog asking for the credentials.
        :returns: A tuple of (hostname, username and session token) string if the user authenticated
                  None if the user cancelled.
        """
        if self.exec_() == QtGui.QDialog.Accepted:
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
            self._new_session_token = session_cache.generate_session_token(
                site, login, password, self._http_proxy
            )
        except AuthenticationError, e:
            # authentication did not succeed
            self._set_error_message(e[0])
            self.ui.message.show()
            return
        finally:
            # restore the cursor
            QtGui.QApplication.restoreOverrideCursor()
            QtGui.QApplication.processEvents()        # dialog is done
        self.accept()
