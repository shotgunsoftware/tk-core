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

import os
from mock import patch

from tank_test.tank_test_base import TankTestBase
from tank_test.tank_test_base import setUpModule # noqa

from tank.authentication import session_cache
from tank.util import LocalFileStorageManager
from tank_vendor import yaml


class SessionCacheTests(TankTestBase):

    def test_current_host(self):
        """
        Makes sure current host is saved appropriately.
        """
        # Write the host and make sure we read it back.
        # Use mixed case to make sure we are case preserving
        host = "https://hOsT.shotgunstudio.com"
        session_cache.set_current_host(host)
        self.assertEqual(session_cache.get_current_host(), host)

        # Update the host and make sure we read it back.
        other_host = "https://other_host.shotgunstudio.com"
        session_cache.set_current_host(other_host)
        self.assertEqual(session_cache.get_current_host(), other_host)

    def test_url_cleanup(self):

        # Make sure that if a file has the url saved incorrectly...
        with patch("sgtk.util.shotgun.connection.sanitize_url", wraps=lambda x: x):
            session_cache.set_current_host("https://host.cleaned.up.on.read/")
            # ... then sure we indeed disabled cleanup and that the malformed value was written to disk...
            self.assertEquals("https://host.cleaned.up.on.read/", session_cache.get_current_host())

        # ... and finaly that the value is filtered when being read back from disk.
        self.assertEquals("https://host.cleaned.up.on.read", session_cache.get_current_host())

        # Make sure we're cleaning up the hostname when saving it.
        session_cache.set_current_host("https://host.cleaned.up.on.write/")

        with open(
            os.path.join(
                LocalFileStorageManager.get_global_root(
                    LocalFileStorageManager.CACHE
                ),
                "authentication.yml"
            ),
            "r"
        ) as fh:
            # Let's read the file directly to see if the data was cleaned up.
            data = yaml.load(fh)
            self.assertEqual(data, {"current_host": "https://host.cleaned.up.on.write"})

    def test_current_user(self):
        """
        Makes sure the current user is saved appropriately for a given host.
        """

        host = "https://host.shotgunstudio.com"
        # Use mixed case to make sure we are case preserving
        user = "BoB"

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

    def test_login_case_insensitivity(self):
        """
        Make sure that the login name comparison in the session cache is case insensitive.
        """
        host = "https://case_insensitive.shotgunstudio.com"
        lowercase_bob = "bob"
        uppercase_bob = "BOB"
        session_token = "123"
        session_data = {
            "login": lowercase_bob,
            "session_token": session_token
        }

        # Store using lower
        session_cache.cache_session_data(
            host,
            lowercase_bob,
            session_token
        )

        # Same inputs should resolve the token.
        self.assertEqual(
            session_cache.get_session_data(host, lowercase_bob),
            session_data
        )

        # upper case user should still recover the session token.
        self.assertEqual(
            session_cache.get_session_data(host, uppercase_bob),
            session_data
        )

        # Deleting with the upper case user should also work.
        session_cache.delete_session_data(host, uppercase_bob)

        # Should not be able to resolve the user, with any case
        self.assertIsNone(
            session_cache.get_session_data(host, uppercase_bob)
        )
        self.assertIsNone(
            session_cache.get_session_data(host, lowercase_bob),
        )

    def test_host_case_insensitivity(self):
        """
        Make sure that the host name case doesn't impact the cache.
        """
        lowercase_host = "https://host.shotgunstudio.com"
        uppercase_host = lowercase_host.upper()

        user = "bob"
        session_token = "123"
        session_data = {
            "login": user,
            "session_token": session_token
        }

        # Store using lower case
        session_cache.cache_session_data(
            lowercase_host,
            user,
            session_token
        )

        # Same inputs should resolve the token.
        self.assertEqual(
            session_cache.get_session_data(lowercase_host, user),
            session_data
        )

        # upper case user should still recover the session token.
        self.assertEqual(
            session_cache.get_session_data(uppercase_host, user),
            session_data
        )

        # Deleting with the upper case user should also work.
        session_cache.delete_session_data(uppercase_host, user)

        # Should not be able to resolve the user, with any case
        self.assertIsNone(
            session_cache.get_session_data(uppercase_host, user)
        )
        self.assertIsNone(
            session_cache.get_session_data(lowercase_host, user),
        )
