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

from tank_vendor.shotgun_authentication import user


class UserTests(TankTestBase):

    def test_serialize_deserialize(self):
        """
        Makes sure serialization and deserialization works for users
        """
        su = user.SessionUser(
            host="host",
            login="login",
            session_token="session_token",
            http_proxy="http_proxy"
        )
        su_2 = user.deserialize_user(user.serialize_user(su))
        self.assertEquals(su.get_host(), su_2.get_host())
        self.assertEquals(su.get_http_proxy(), su_2.get_http_proxy())
        self.assertEquals(su.get_login(), su_2.get_login())
        self.assertEquals(su.get_session_token(), su_2.get_session_token())

        su = user.ScriptUser(
            host="host",
            api_script="api_script",
            api_key="api_key",
            http_proxy="http_proxy"
        )

        su_2 = user.deserialize_user(user.serialize_user(su))
        self.assertEquals(su.get_host(), su_2.get_host())
        self.assertEquals(su.get_http_proxy(), su_2.get_http_proxy())
        self.assertEquals(su.get_key(), su_2.get_key())
        self.assertEquals(su.get_script(), su_2.get_script())
