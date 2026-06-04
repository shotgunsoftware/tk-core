# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
)

from tank_test.tank_test_base import setUpModule  # noqa

from tank.authentication import session_cache
from tank.util import LocalFileStorageManager
from tank_vendor import yaml


class SessionCacheTests(ShotgunTestBase):
    def setUp(self):
        super().setUp()
        # Wipe the global session file that has been edited by previous tests.
        self._write_global_yml({})

    def _write_global_yml(self, content):
        """
        Writes the global authentication file.
        """
        session_cache._write_yaml_file(
            session_cache._get_global_authentication_file_location(), content
        )

    def _write_site_yml(self, site, content):
        """
        Writes the site authentication file.
        """
        session_cache._write_yaml_file(
            session_cache._get_site_authentication_file_location(site), content
        )

    def _clear_site_yml(self, site):
        """
        Clears the site authentication file.
        """
        self._write_site_yml(site, {})

    def test_recent_users_upgrade(self):
        pass
    def test_recent_hosts_upgrade(self):
        pass
    def test_recent_users_downgrade(self):
        pass
    def test_recent_hosts_downgrade(self):
        pass
    def test_recent_hosts(self):
        pass
    def test_recent_users(self):
        pass
    def test_current_host(self):
        pass
    def test_url_cleanup(self):
        pass
    def test_current_user(self):
        pass
    def test_session_cache(self):
        pass
    def test_login_case_insensitivity(self):
        pass
    def test_host_case_insensitivity(self):
        pass
