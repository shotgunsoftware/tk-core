# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.


import sys

from tank_test.tank_test_base import *
from mock import patch
import tank
import tank_vendor


@skip_if_pyside_missing
class LoginUiTests(TankTestBase):

    def setUp(self, *args, **kwargs):
        """
        Adds Qt modules to tank.platform.qt and initializes QApplication
        """
        from PySide import QtGui
        # Only configure qApp once, it's a singleton.
        if QtGui.qApp is None:
            self._app = QtGui.QApplication(sys.argv)
        super(LoginUiTests, self).setUp()

    def test_site_and_user_disabled_on_session_renewal(self):
        """
        Make sure that the site and user fields are disabled when doing session renewal
        """
        from tank_vendor.shotgun_authentication.ui.login_dialog import LoginDialog
        ld = LoginDialog("Dummy", is_session_renewal=True)
        self.assertTrue(ld.ui.site.isReadOnly())
        self.assertTrue(ld.ui.login.isReadOnly())

    def _prepare_mocks(
        self,
        get_connection_information_mock,
        cache_connection_information_mock
    ):
        """
        Configures all the mocks for the two interactive unit tests.
        :param get_connection_information_mock: Mock for the tank.util.authentication.get_connection_information_mock
        :param cache_connection_information_mock: Mock for the tank.util.authentication.cache_connection_information_mock
        """
        get_connection_information_mock.return_value = {
            "host": "https://enter_your_host_name_here.shotgunstudio.com",
            "login": "enter_your_username_here"
        }
        cache_connection_information_mock.return_value = None

    @patch("tank_vendor.shotgun_authentication.authentication.cache_connection_information")
    @patch("tank_vendor.shotgun_authentication.authentication.get_connection_information")
    @interactive
    def test_interactive_login(self, *args):
        """
        Pops the ui and lets the user authenticate.
        """
        self._prepare_mocks(*args)

        tank_vendor.shotgun_authentication.interactive_authentication.authenticate()
