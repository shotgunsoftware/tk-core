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

from tank_test.tank_test_base import ShotgunTestBase
from tank_test.tank_test_base import setUpModule # noqa

from tank.authentication import session_cache
from tank.util import LocalFileStorageManager
from tank_vendor import yaml


class SessionCacheTests(ShotgunTestBase):

    def setUp(self):
        super(SessionCacheTests, self).setUp()
        # Wipe the global session file that has been edited by previous tests.
        self._write_global_yml({})

    def _write_global_yml(self, content):
        """
        Writes the global authentication file.
        """
        session_cache._write_yaml_file(
            session_cache._get_global_authentication_file_location(),
            content
        )

    def _write_site_yml(self, site, content):
        """
        Writes the site authentication file.
        """
        session_cache._write_yaml_file(
            session_cache._get_site_authentication_file_location(site),
            content
        )

    def _clear_site_yml(self, site):
        """
        Clears the site authentication file.
        """
        self._write_site_yml(site, {})

    def test_recent_users_upgrade(self):
        """
        Ensures that if we've just upgraded to the latest core that the current
        user is part of the recent users.
        """
        HOST = "https://host.shotgunstudio.com"

        # The recent_users array is not present in the authentication.yml
        # file, so make sure that the session cache reports the user as the
        # most recent.
        self._write_site_yml(
            HOST, {"current_user": "current.user", "users": []}
        )

        self.assertEqual(
            session_cache.get_recent_users(HOST),
            ["current.user"]
        )

    def test_recent_hosts_upgrade(self):
        """
        Ensures that if we've just upgraded to the latest core that the current
        host is part of the recent hosts.
        """
        # The recent_users array is not present in the authentication.yml
        # file, so make sure that the session cache reports the user as the
        # most recent.
        self._write_global_yml(
            {"current_host": "https://host.shotgunstudio.com"}
        )

        self.assertEqual(
            session_cache.get_recent_hosts(),
            ["https://host.shotgunstudio.com"]
        )

    def test_recent_users_downgrade(self):
        """
        Ensures that if an older core updated the authentication file, which means
        recent_users has not been kept up to date, that the recent users list
        has the current_user at the front.
        """
        HOST = "https://host.shotgunstudio.com"
        self._write_site_yml(
            HOST,
            {"current_user": "current.user", "recent_users": ["older.user", "current.user"]}
        )

        self.assertEqual(
            session_cache.get_recent_users(HOST), ["current.user", "older.user"]
        )

    def test_recent_hosts_downgrade(self):
        """
        Ensures that if an older core updated the authentication file, which means
        recent_hosts has not been kept up to date, that the recent hosts list
        has the current_host at the front.
        """
        self._write_global_yml(
            {"current_host": "https://current.shotgunstudio.com",
             "recent_hosts": ["https://older.shotgunstudio.com", "https://current.shotgunstudio.com"]}
        )

        self.assertEqual(
            session_cache.get_recent_hosts(), [
                "https://current.shotgunstudio.com",
                "https://older.shotgunstudio.com"
            ]
        )

    def test_recent_hosts(self):
        """
        Makes sure the recent hosts list is keep up to date.
        """
        HOST_A = "https://host-a.shotgunstudio.com"
        HOST_B = "https://host-b.shotgunstudio.com"

        # Make sure the recent hosts is initially empty.
        self.assertEqual(session_cache.get_recent_hosts(), [])

        # Set HOST_A as the current host.
        session_cache.set_current_host(HOST_A)
        self.assertEqual(session_cache.get_recent_hosts(), [HOST_A])
        self.assertEqual(session_cache.get_current_host(), HOST_A)

        # Then set HOST_B as the new current host.
        session_cache.set_current_host(HOST_B)
        self.assertEqual(session_cache.get_recent_hosts(), [HOST_B, HOST_A])
        self.assertEqual(session_cache.get_current_host(), HOST_B)

        # Now set back HOST_A as the current host. It should now be the most recent.
        session_cache.set_current_host(HOST_A)
        self.assertEqual(session_cache.get_recent_hosts(), [HOST_A, HOST_B])
        self.assertEqual(session_cache.get_current_host(), HOST_A)

        # Update the cache 10 times.
        n_hosts = ["https://host-%d.shotgunstudio.com" % i for i in range(10)]
        for host in n_hosts:
            session_cache.set_current_host(host)

        # We should now have hosts 9 down to 2 in the most recent list.
        most_recents = ["https://host-%d.shotgunstudio.com" % i for i in range(9, 1, -1)]

        self.assertEqual(session_cache.get_recent_hosts(), most_recents)

    def test_recent_users(self):
        """
        Makes sure the recent hosts list is keep up to date.
        """
        HOST = "https://host.shotgunstudio.com"
        LOGIN_A = "login_a"
        LOGIN_B = "login_b"

        self._clear_site_yml(HOST)

        # Make sure the recent hosts is initially empty.
        self.assertEqual(session_cache.get_recent_users(HOST), [])

        # Set HOST_A as the current host.
        session_cache.set_current_user(HOST, LOGIN_A)
        self.assertEqual(session_cache.get_recent_users(HOST), [LOGIN_A])
        self.assertEqual(session_cache.get_current_user(HOST), LOGIN_A)

        # Then set HOST_B as the new current host.
        session_cache.set_current_user(HOST, LOGIN_B)
        self.assertEqual(session_cache.get_recent_users(HOST), [LOGIN_B, LOGIN_A])
        self.assertEqual(session_cache.get_current_user(HOST), LOGIN_B)

        # Now set back HOST_A as the current host. It should now be the most recent.
        session_cache.set_current_user(HOST, LOGIN_A)
        self.assertEqual(session_cache.get_recent_users(HOST), [LOGIN_A, LOGIN_B])
        self.assertEqual(session_cache.get_current_user(HOST), LOGIN_A)

        # Update the cache 10 times.
        n_users = ["login-%d" % i for i in range(10)]
        for user in n_users:
            session_cache.set_current_user(HOST, user)

        # We should now have users 9 down to 2 in the most recent list.
        most_recents = ["login-%d" % i for i in range(9, 1, -1)]

        self.assertEqual(session_cache.get_recent_users(HOST), most_recents)

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
            self.assertEqual(
                data["current_host"],
                "https://host.cleaned.up.on.write"
            )

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
            "bob_session_token",
            "bob_session_metadata"
        )
        self.assertEqual(
            session_cache.get_session_data(host, "bob")["session_token"], "bob_session_token"
        )
        self.assertEqual(
            session_cache.get_session_data(host, "bob")["session_metadata"], "bob_session_metadata"
        )

        # Make sure we can store a second one.
        session_cache.cache_session_data(
            host,
            "alice",
            "alice_session_token",
            "alice_session_metadata"
        )
        # We can see the old one
        self.assertEqual(
            session_cache.get_session_data(host, "bob")["session_token"], "bob_session_token"
        )
        self.assertEqual(
            session_cache.get_session_data(host, "bob")["session_metadata"], "bob_session_metadata"
        )
        # check for the new one
        self.assertEqual(
            session_cache.get_session_data(host, "alice")["session_token"], "alice_session_token"
        )
        self.assertEqual(
            session_cache.get_session_data(host, "alice")["session_metadata"], "alice_session_metadata"
        )

        session_cache.delete_session_data(host, "bob")

        self.assertEqual(session_cache.get_session_data(host, "bob"), None)
        self.assertEqual(
            session_cache.get_session_data(host, "alice")["session_token"], "alice_session_token"
        )
        self.assertEqual(
            session_cache.get_session_data(host, "alice")["session_metadata"], "alice_session_metadata"
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
