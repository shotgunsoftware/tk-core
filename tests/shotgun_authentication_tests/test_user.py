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

from tank_test.tank_test_base import *

from mock import patch

from tank_vendor.shotgun_authentication import user, user_impl
from tank_vendor.shotgun_api3 import AuthenticationFault


class Success(Exception):
    """
    We'll use this to break the execution of the code. Since we don't
    actually call the server to retrieve information, we can't let
    the _call_rpc mock return to the caller. If we raise this exception
    from a test, it will signify that we are happy with how _call_rpc
    was invoked and that the test succeeded.
    """
    pass


class UserTests(TankTestBase):

    def _create_test_user(self):
        return user.ShotgunUser(user_impl.SessionUser(
            host="https://tank.shotgunstudio.com",
            login="login",
            session_token="session_token",
            http_proxy="http_proxy"
        ))

    def test_serialize_deserialize(self):
        """
        Makes sure serialization and deserialization works for users
        """
        su = self._create_test_user()
        su_2 = user.deserialize_user(user.serialize_user(su))
        self.assertEquals(su.host, su_2.host)
        self.assertEquals(su.http_proxy, su_2.http_proxy)
        self.assertEquals(su.login, su_2.login)
        self.assertEquals(su.impl.get_session_token(), su_2.impl.get_session_token())

        su = user.ShotgunUser(user_impl.ScriptUser(
            host="host",
            api_script="api_script",
            api_key="api_key",
            http_proxy="http_proxy"
        ))

        su_2 = user.deserialize_user(user.serialize_user(su))
        self.assertEquals(su.host, su_2.host)
        self.assertEquals(su.http_proxy, su_2.http_proxy)
        self.assertEquals(su.login, su_2.login)
        self.assertEquals(su.impl.get_key(), su_2.impl.get_key())
        self.assertEquals(su.impl.get_script(), su_2.impl.get_script())

    @patch("tank_vendor.shotgun_api3.Shotgun._call_rpc")
    @patch("tank_vendor.shotgun_authentication.interactive_authentication.renew_session")
    def test_refresh_credentials_failure(self, renew_session_mock, call_rpc_mock):
        """
        Makes sure we can refresh credentials correctly.

        :param renew_session_mock: Mock for the renew_session method in interactive_authentication.
        :param renew_session_mock: Mock for the _call_rpc method on the Shotgun class.
        """

        su = self._create_test_user()

        # First make sure we are failing if the session is not renewed correctly.
        call_rpc_mock.side_effect = AuthenticationFault()
        sg = su.create_sg_connection()
        with self.assertRaises(AuthenticationFault):
            sg._call_rpc()

    @patch("tank_vendor.shotgun_api3.Shotgun._call_rpc")
    @patch("tank_vendor.shotgun_authentication.interactive_authentication.renew_session")
    def test_refresh_credentials_on_old_connection(self, renew_session_mock, call_rpc_mock):
        """
        Makes sure that an existing connection with old session token can still be
        refreshed with the newer token on the user object.

        :param renew_session_mock: Mock for the renew_session method in interactive_authentication.
        :param renew_session_mock: Mock for the _call_rpc method on the Shotgun class.
        """

        su = self._create_test_user()

        # Simulate a session renewal has happened since the Shotgun connection
        # creationg
        sg = su.create_sg_connection()
        su.impl.set_session_token("session_token_2")

        # Make sure the Shotgun instance still has the old value.
        self.assertEqual(sg.config.session_token, "session_token")

        # Trigger _call_rpc to make sure sure the ShotgunWrapper copied over the session_token.
        sg._call_rpc()
        self.assertEqual(sg._user.get_session_token(), "session_token_2")
