# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import with_statement
from mock import patch

from tank_test.tank_test_base import *

from tank.util import login


class LoginTests(TankTestBase):
    """
    Tests the login module.
    """

    @patch("tank_test.mockgun.Shotgun.find_one")
    @patch("tank_vendor.shotgun_authentication.authentication.is_script_user_authenticated")
    @patch("tank_vendor.shotgun_authentication.authentication.is_human_user_authenticated")
    @patch("tank_vendor.shotgun_authentication.authentication.get_connection_information")
    def test_get_current_user_uses_session(
        self,
        get_connection_information_mock,
        is_human_user_authenticated_mock,
        is_script_user_authenticated_mock,
        find_one_mock
    ):
        """
        When we are session based, the get_current_user method should return user associated to the
        session.
        """
        find_one_mock.return_value = {
            "login": "tk-user"
        }
        is_human_user_authenticated_mock.return_value = True
        is_script_user_authenticated_mock.return_value = False
        get_connection_information_mock.return_value = {
            "login": "tk-user"
        }
        try:
            # Clear the cache so that get_current_user can work. Path cache is being updated by
            # TankTestBase.setUp which calls get_current_user when nothing is authenticated yet
            # so we need to uncache the value for the test
            current_user = tank.util.login.g_shotgun_current_user_cache
            tank.util.login.g_shotgun_current_user_cache = "unknown"
            user = login.get_current_user(self.tk)
            self.assertEqual(user["login"], "tk-user")
        finally:
            # Make sure we ene up back in the original state of no new side effects are introduced in the tests.
            tank.util.login.g_shotgun_current_user_cache = current_user
