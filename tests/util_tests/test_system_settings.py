# Copyright (c) 2016 Shotgun Software Inc.
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

from tank_test.tank_test_base import ShotgunTestBase
from tank_test.tank_test_base import setUpModule # noqa

from mock import patch

from tank.util.system_settings import SystemSettings


class SystemSettingsTests(ShotgunTestBase):
    """
    Tests functionality from the SystemSettings class.
    """

    def test_system_proxy(self):
        """
        Tests the fallback on the operating system http proxy.
        """
        http_proxy = "foo:bar@74.50.63.111:80"  # IP address of shotgunstudio.com

        with patch.dict(os.environ, {"http_proxy": "http://" + http_proxy}):
            settings = SystemSettings()
            self.assertEqual(settings.http_proxy, http_proxy)
