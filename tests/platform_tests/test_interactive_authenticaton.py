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


@skip_if_pyside_missing
class LoginUiTests(TankTestBase):

    def setUp(self, *args, **kwargs):
        """
        Adds Qt modules to tank.platform.qt and initializes QApplication
        """
        from PySide import QtGui, QtCore
        # Only configure qApp once, it's a singleton.
        if QtGui.qApp is None:
            self._app = QtGui.QApplication(sys.argv)

        tank.platform.qt.QtCore = QtCore
        tank.platform.qt.QtGui = QtGui

    def tearDown(self):
        """
        Removes Qt modules from tank.platform.qt
        """
        del tank.platform.qt.QtCore
        del tank.platform.qt.QtGui

    def test_site_and_user_disabled_on_session_renewal(self):
        """
        Make sure that the site and user fields are disabled when doing session renewal
        """
        from tank.platform.qt.login_dialog import LoginDialog
        ld = LoginDialog("Dummy", session_renewal=True)
        self.assertTrue(ld.ui.site.isReadOnly())
        self.assertTrue(ld.ui.login.isReadOnly())

    def _prepare_mocks(
        self,
        is_authenticated_mock,
        get_associated_sg_config_data_mock,
        get_login_info_mock,
        cache_session_data_mock
    ):
        """
        Configures all the mocks for the two interactive unit tests.
        :param is_authenticated_mock: Mock for the tank.util.authentication.is_authenticated method.
        :param get_associated_sg_config_data_mock: Mock for the tank.util.shotgun.get_associated_sg_config_data
        :param get_login_info_mock: Mock for the tank.util.authentication.get_login_info
        :param cache_session_data_mock: Mock for the tank.util.authentication.cache_session_data
        """
        is_authenticated_mock.return_value = False
        get_associated_sg_config_data_mock.return_value = {
            "host": "https://something.shotgunstudio.com"
        }
        get_login_info_mock.return_value = {
            "login": "someone"
        }
        cache_session_data_mock.return_value = None

    @patch("tank.util.authentication.cache_session_data")
    @patch("tank.util.authentication.get_login_info")
    @patch("tank.util.shotgun.get_associated_sg_config_data")
    @patch("tank.util.authentication.is_authenticated")
    @interactive
    def test_interactive_login(self, *args):
        """
        Pops the ui and lets the user authenticate.
        """
        self._prepare_mocks(*args)

        tank.platform.interactive_authentication.ui_authenticate()
