# -*- coding: utf-8 -*-

# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.
from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import ShotgunTestBase

from tank.authentication.sso_saml2.core.utils import get_user_name, _encode_cookies


class SamlSsoCoreUtilsTests(ShotgunTestBase):

    def test_username_valid(self):
        login_cookies = {
            'user+name': 'shotgun_current_user_login=user%2Bname; domain=shotgrid.autodesk.com; path=/',
            'user name': 'shotgun_current_user_login=user+name; domain=shotgrid.autodesk.com; path=/'
        }
        for login in login_cookies:
            self.assertEqual(login, get_user_name(_encode_cookies(login_cookies[login])))
