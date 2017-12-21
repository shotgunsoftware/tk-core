# Copyright (c) 2017 Shotgun Software Inc.
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
from mock import MagicMock, patch

from tank_test.tank_test_base import setUpModule # noqa
from tank_test.tank_test_base import TankTestBase

from sgtk.bootstrap.configuration import Configuration
import sgtk


class TestConfiguration(TankTestBase):

    def setUp(self):
        """
        Overrides get_default_user so it returns something.
        """
        super(TestConfiguration, self).setUp()

        self._mock_default_user = MagicMock()

        patcher = patch(
            "tank.authentication.ShotgunAuthenticator.get_default_user",
            return_value=self._mock_default_user
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_login_based_authentication(self):
        """
        Ensure the configuration will always pick the user passed in when there is no script user.
        """
        configuration = Configuration(None, None)

        self._mock_default_user.login = "user"

        user = MagicMock(login="another_user")
        configuration._set_authenticated_user(user)

        self.assertEqual(sgtk.get_authenticated_user(), user)

    def test_script_based_authentication(self):
        """
        Ensure the configuration will always pick the script user when the configuration uses one.
        """
        configuration = Configuration(None, None)

        self._mock_default_user.login = None

        user = MagicMock(login="another_user")
        configuration._set_authenticated_user(user)

        self.assertEqual(
            sgtk.get_authenticated_user(), self._mock_default_user
        )


class TestInvalidInstalledConfiguration(TankTestBase):
    """
    Tests that error messages are raised at startup when
    the linux/windows/path fields are set to a configuration which
    isn't valid
    """

    def setUp(self):
        super(TestInvalidInstalledConfiguration, self).setUp()
        self._tmp_bundle_cache = os.path.join(self.tank_temp, "bundle_cache")
        self._resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="tk-maya",
            bundle_cache_fallback_paths=[self._tmp_bundle_cache]
        )

    def test_resolve_installed_configuration(self):
        """
        Makes sure an installed configuration is resolved.
        """
        # note: this is using the classic config that is part of the
        #       std test fixtures.
        config = self._resolver.resolve_shotgun_configuration(
            self.tk.pipeline_configuration.get_shotgun_id(),
            "sgtk:descriptor:not?a=descriptor",
            self.tk.shotgun,
            "john.smith"
        )
        self.assertIsInstance(
            config,
            sgtk.bootstrap.resolver.InstalledConfiguration
        )

        self.assertEquals(config.status(), config.LOCAL_CFG_UP_TO_DATE)

        # now get rid of some stuff from our fixtures to emulate
        # a config which was downloaded directly from github and not
        # created by setup_project
        os.remove(
            os.path.join(self.pipeline_config_root, "config", "core", "pipeline_configuration.yml")
        )

        os.remove(
            os.path.join(self.pipeline_config_root, "config", "core", "install_location.yml")
        )


        with self.assertRaisesRegexp(
                sgtk.bootstrap.TankBootstrapError,
                "Cannot find required system file"):
            config.status()


