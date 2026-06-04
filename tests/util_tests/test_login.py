# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from tank_test.tank_test_base import (
    mock,
    TankTestBase,
)

import tank
from tank.util import login
from tank.authentication import ShotgunAuthenticator


class LoginTests(TankTestBase):
    """
    Tests the login module.
    """

    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find_one")
    @mock.patch("tank.api.get_authenticated_user")
    def test_get_current_user_uses_session(
        self, get_authenticated_user_mock, find_one_mock
    ):
        pass
