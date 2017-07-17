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

from tank_test.tank_test_base import TankTestBase
from tank_test.tank_test_base import setUpModule # noqa

from sgtk.authentication.utils import cleanup_url


class UtilsTests(TankTestBase):

    def test_cleanup_urls(self):

        # Ensure https is added if no scheme is specified.
        self.assertEquals(
            "https://no.scheme.com",
            cleanup_url("no.scheme.com")
        )

        # Ensure that port number is also kept.
        self.assertEquals(
            "https://no.scheme.com:8080",
            cleanup_url("no.scheme.com:8080")
        )

        # Ensure https is not modified if specified.
        self.assertEquals(
            "https://no.scheme.com",
            cleanup_url("https://no.scheme.com")
        )

        # Ensure http is left as is if specified.
        self.assertEquals(
            "http://no.scheme.com",
            cleanup_url("http://no.scheme.com")
        )

        # Ensure any scheme is left as is if specified.
        self.assertEquals(
            "invalid-scheme://no.scheme.com",
            cleanup_url("invalid-scheme://no.scheme.com")
        )

        # Ensures a suffixed slash gets removed.
        self.assertEquals(
            "https://no.suffixed.slash.com",
            cleanup_url("https://no.suffixed.slash.com/")
        )

        # Ensures anything after the host is dropped.
        self.assertEquals(
            "https://no.suffixed.slash.com",
            cleanup_url("https://no.suffixed.slash.com/path/to/a/resource")
        )
