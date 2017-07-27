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
from sgtk.authentication import ShotgunAuthenticator
import sgtk


class TestConfiguration(TankTestBase):

    def test_login_based_authentication(self):
        """
        Ensure the configuration will always pick the user passed in when there is no script user.
        """
        configuration = Configuration(None, None)
        sg_auth = ShotgunAuthenticator()

        default_user = sg_auth.create_session_user("default_user", "abcd")

        # Create a default user.
        with patch(
            "tank.authentication.ShotgunAuthenticator.get_default_user",
            return_value=default_user
        ):
            current_user = sg_auth.create_session_user("current_user", "1234")
            configuration._set_authenticated_user(current_user, sgtk.authentication.serialize_user)

            self.assertEqual(sgtk.get_authenticated_user().login, current_user.login)
            self.assertNotEqual(id(sgtk.get_authenticated_user()), id(current_user))

    def test_fail_reinstantiating(self):
        """
        Ensure the configuration will recover if the user can't be serialized/unserialized.
        """
        configuration = Configuration(None, None)
        sg_auth = ShotgunAuthenticator()

        default_user = sg_auth.create_session_user("default_user", "abcd")

        # Create a default user.
        with patch(
            "tank.authentication.ShotgunAuthenticator.get_default_user",
            return_value=default_user
        ):
            serialize_mock = MagicMock()
            serialize_mock.side_effect = Exception("This will be raised.")

            current_user = sg_auth.create_session_user("current_user", "1234")
            configuration._set_authenticated_user(current_user, serialize_mock)

            self.assertEqual(sgtk.get_authenticated_user().login, current_user.login)
            self.assertEqual(id(sgtk.get_authenticated_user()), id(current_user))

    def test_script_based_authentication(self):
        """
        Ensure the configuration will always pick the script user when the configuration uses one.
        """
        configuration = Configuration(None, None)
        sg_auth = ShotgunAuthenticator()

        script_user = sg_auth.create_script_user("api_script", "api_key")

        # Create a default user.
        with patch(
            "tank.authentication.ShotgunAuthenticator.get_default_user",
            return_value=script_user
        ):
            current_user = sg_auth.create_session_user("current_user", "1234")
            configuration._set_authenticated_user(current_user, sgtk.authentication.serialize_user)

            self.assertEqual(id(sgtk.get_authenticated_user()), id(script_user))
