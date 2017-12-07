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
import uuid

from tank_test.tank_test_base import TankTestBase
from tank_test.tank_test_base import setUpModule # noqa

from mock import patch

from tank.util import EnvironmentVariableFileLookupError
from tank.util.user_settings import UserSettings
from sgtk import TankError


class UserSettingsTests(TankTestBase):
    """
    Tests functionality around toolkit.ini
    """

    def setUp(self):
        """
        Make sure the singleton is reset at the beginning of this test.
        """
        super(UserSettingsTests, self).setUp()
        UserSettings.clear_singleton()
        self.addCleanup(UserSettings.clear_singleton)

    def _mock_ini_file(self, login_section={}, custom_section={}):
        """
        Creates an ini file in a unique location with te user settings.

        :param login_section: Dictionary of settings that will be stored in the [Login] section.
        :param custom_section: Dictionary of settings that will be stored in the [Custom] section.
        """
        # Create a unique folder for this test.
        folder = os.path.join(self.tank_temp, str(uuid.uuid4()))
        os.makedirs(folder)

        # Manually write the file as this is the format we're expecting the UserSettings
        # to parse.

        ini_file_location = os.path.join(folder, "toolkit.ini")
        with open(ini_file_location, "w") as f:
            f.writelines(["[Login]\n"])
            for key, value in login_section.iteritems():
                f.writelines(["%s=%s\n" % (key, value)])

            f.writelines(["[Custom]\n"])
            for key, value in custom_section.iteritems():
                f.writelines(["%s=%s\n" % (key, value)])

        # The setUp phase cleared the singleton. So set the preferences environment variable and
        # instantiate the singleton, which will read the env var and open that location.
        with patch.dict(os.environ, {"SGTK_PREFERENCES_LOCATION": ini_file_location}):
            UserSettings()

    def test_empty_file(self):
        """
        Tests a complete yaml file.
        """
        settings = UserSettings()
        self.assertIsNone(settings.default_site)
        self.assertIsNone(settings.default_login)
        self.assertIsNone(settings.shotgun_proxy)
        self.assertIsNone(settings.app_store_proxy)

    def test_filled_file(self):
        """
        Tests a complete yaml file.
        """
        self._mock_ini_file({
            "default_site": "site",
            "default_login": "login",
            "http_proxy": "http_proxy",
            "app_store_http_proxy": "app_store_http_proxy"
        })

        settings = UserSettings()
        self.assertEqual(settings.default_site, "site")
        self.assertEqual(settings.default_login, "login")
        self.assertEqual(settings.shotgun_proxy, "http_proxy")
        self.assertEqual(settings.app_store_proxy, "app_store_http_proxy")

    def test_empty_settings(self):
        """
        Tests a yaml file with the settings present but empty.
        """
        self._mock_ini_file({
            "default_site": "",
            "default_login": "",
            "http_proxy": "",
            "app_store_http_proxy": ""
        })

        settings = UserSettings()
        self.assertEqual(settings.default_site, "")
        self.assertEqual(settings.default_login, "")
        self.assertEqual(settings.shotgun_proxy, "")
        self.assertEqual(settings.app_store_proxy, "")

    def test_custom_settings(self):
        """
        Tests that we can read settings in any section of the file.
        """

        self._mock_ini_file(
            custom_section={
                "custom_key": "custom_value"
            }
        )

        self.assertEqual(
            UserSettings().get_setting("Custom", "custom_key"),
            "custom_value"
        )

    def test_boolean_setting(self):
        """
        Tests that we can read a setting into a boolean.
        """
        self._mock_ini_file(
            custom_section={
                "valid": "ON",
                "invalid": "L"
            }
        )

        self.assertEqual(
            UserSettings().get_boolean_setting("Custom", "valid"), True
        )
        with self.assertRaisesRegexp(
            TankError,
            "Invalid value 'L' in '.*' for setting 'invalid' in section 'Custom': expecting one of .*."
        ):
            UserSettings().get_boolean_setting("Custom", "invalid")

    def test_integer_setting(self):
        """
        Tests that we can read a setting into an integer
        """

        self._mock_ini_file(
            custom_section={
                "valid": "1",
                "also_valid": "-1",
                "invalid": "L"
            }
        )

        self.assertEqual(
            UserSettings().get_integer_setting("Custom", "valid"), 1
        )
        self.assertEqual(
            UserSettings().get_integer_setting("Custom", "also_valid"), -1
        )
        with self.assertRaisesRegexp(
            TankError,
            "Invalid value 'L' in '.*' for setting 'invalid' in section 'Custom': expecting integer."
        ):
            UserSettings().get_integer_setting("Custom", "invalid")

    def test_environment_variable_expansions(self):
        """
        Tests that setting an environment variable will be resolved.
        """
        self._mock_ini_file({
            # Config parser represent empty settings as empty strings
            "default_site": "https://${SGTK_TEST_SHOTGUN_SITE}.shotgunstudio.com"
        })
        with patch.dict(os.environ, {"SGTK_TEST_SHOTGUN_SITE": "shotgun_site"}):
            settings = UserSettings()
            self.assertEqual(settings.default_site, "https://shotgun_site.shotgunstudio.com")

    def test_bad_environment_variable(self):
        """
        Test environment variables being set to files that don't exist.
        """
        with patch.dict(os.environ, {"SGTK_PREFERENCES_LOCATION": "/a/b/c"}):
            with self.assertRaisesRegexp(EnvironmentVariableFileLookupError, "/a/b/c"):
                UserSettings()

        with patch.dict(os.environ, {"SGTK_DESKTOP_CONFIG_LOCATION": "/d/e/f"}):
            with self.assertRaisesRegexp(EnvironmentVariableFileLookupError, "/d/e/f"):
                UserSettings()
