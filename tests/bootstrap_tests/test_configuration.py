# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import with_statement

from mock import MagicMock, patch

from tank_test.tank_test_base import setUpModule # noqa
from tank_test.tank_test_base import TankTestBase

from sgtk.bootstrap.configuration import Configuration
import sgtk


class TestConfiguration(TankTestBase):

    def setUp(self):
        """
        Overrides get_default_user so it returns something.
        """
        super(TestConfiguration, self).setUp()

        self._mock_default_user = MagicMock()

        patcher = patch(
            "tank.authentication.ShotgunAuthenticator.get_default_user",
            return_value=self._mock_default_user
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_login_based_authentication(self):
        """
        Ensure the configuration will always pick the user passed in when there is no script user.
        """
        configuration = Configuration(None, None)

        self._mock_default_user.login = "user"

        user = MagicMock(login="another_user")
        configuration._set_authenticated_user(user)

        self.assertEqual(sgtk.get_authenticated_user(), user)

    def test_script_based_authentication(self):
        """
        Ensure the configuration will always pick the script user when the configuration uses one.
        """
        configuration = Configuration(None, None)

        self._mock_default_user.login = None

        user = MagicMock(login="another_user")
        configuration._set_authenticated_user(user)

        self.assertEqual(
            sgtk.get_authenticated_user(), self._mock_default_user
        )
