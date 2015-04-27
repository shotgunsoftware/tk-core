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

from tank_vendor.shotgun_authentication import session_cache


class SessionCacheTests(TankTestBase):

    def test_current_host(self):
        """
        Makes sure current host is saved appropriately.
        """
        # Write the host and make sure we read it back.
        host = "https://host.shotgunstudio.com"
        session_cache.set_current_host(host)
        self.assertEqual(session_cache.get_current_host(), host)

        # Update the host and make sure we read it back.
        other_host = "https://other_host.shotgunstudio.com"
        session_cache.set_current_host(other_host)
        self.assertEqual(session_cache.get_current_host(), other_host)

    def test_current_user(self):
        """
        Makes sure the current user is saved appropriately for a given host.
        """

        host = "https://host.shotgunstudio.com"
        user = "bob"

        # Write the current user for a host and makes sure we get it back.
        session_cache.set_current_user(host, user)
        self.assertEqual(session_cache.get_current_user(host), user)

        # Write the current user for a second host and make sure we get it
        # back. Also make sure we are not updating the other host for some
        # reason.
        other_host = "https://other_host.shotgunstudio.com"
        other_user = "alice"
        session_cache.set_current_user(other_host, other_user)
        self.assertEqual(session_cache.get_current_user(other_host), other_user)
        self.assertEqual(session_cache.get_current_user(host), user)

    def test_session_cache(self):
        """
        Makes sure that the user enabled sessions are stored properly.
        """

        # Make sure we stored the session token.
        host = "https://host.shotgunstudio.com"
        session_cache.cache_session_data(
            host,
            "bob",
            "bob_session_token"
        )
        self.assertEqual(
            session_cache.get_session_data(host, "bob")["session_token"], "bob_session_token"
        )

        # Make sure we can store a second one.
        session_cache.cache_session_data(
            host,
            "alice",
            "alice_session_token"
        )
        # We can see the old one
        self.assertEqual(
            session_cache.get_session_data(host, "bob")["session_token"], "bob_session_token"
        )
        # check for the new one
        self.assertEqual(
            session_cache.get_session_data(host, "alice")["session_token"], "alice_session_token"
        )

        session_cache.delete_session_data(host, "bob")

        self.assertEqual(session_cache.get_session_data(host, "bob"), None)
        self.assertEqual(
            session_cache.get_session_data(host, "alice")["session_token"], "alice_session_token"
        )
