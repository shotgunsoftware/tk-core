# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

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
from mock import patch

from tank_test.tank_test_base import setUpModule # noqa
from tank_test.tank_test_base import TankTestBase

from sgtk.bootstrap.configuration import Configuration
from sgtk.authentication import ShotgunAuthenticator
import sgtk


class TestConfiguration(TankTestBase):

    def _create_session_user(self, name):
        """
        Shorthand to create a session user.
        """
        return ShotgunAuthenticator().create_session_user(
            name, session_token=name[::-1], host="https://test.shotgunstudio.com"
        )

    def _create_script_user(self, api_script):
        """
        Shorthand to create a script user.
        """
        return ShotgunAuthenticator().create_script_user(
            api_script, api_key=api_script[::-1], host="https://test.shotgunstudio.com"
        )

    def test_login_based_authentication(self):
        """
        Ensure the configuration will always pick the user passed in when there is no script user.
        """
        configuration = Configuration(None, None)

        default_user = self._create_session_user("default_user")

        # Create a default user.
        with patch(
            "tank.authentication.ShotgunAuthenticator.get_default_user",
            return_value=default_user
        ):
            current_user = self._create_session_user("current_user")
            configuration._set_authenticated_user(
                current_user,
                sgtk.authentication.serialize_user(current_user)
            )

            self.assertEqual(sgtk.get_authenticated_user().login, current_user.login)
            self.assertNotEqual(id(sgtk.get_authenticated_user()), id(current_user))

    def test_fail_reinstantiating(self):
        """
        Ensure the configuration will recover if the user can't be serialized/unserialized.
        """
        configuration = Configuration(None, None)

        default_user = self._create_session_user("default_user")

        # Create a default user.
        with patch(
            "tank.authentication.ShotgunAuthenticator.get_default_user",
            return_value=default_user
        ):
            # Python 2.6 doesn't support multi-expression with statement, so nest the calls instead.
            with patch(
                "tank.authentication.deserialize_user",
                wraps=sgtk.authentication.user.deserialize_user
            ) as deserialize_wrapper:
                current_user = self._create_session_user("current_user")
                configuration._set_authenticated_user(current_user, "invalid")

                deserialize_wrapper.assert_called_once_with("invalid")

                self.assertEqual(sgtk.get_authenticated_user().login, current_user.login)
                self.assertEqual(id(sgtk.get_authenticated_user()), id(current_user))

    def test_script_based_authentication(self):
        """
        Ensure the configuration will always pick the script user when the configuration uses one.
        """
        configuration = Configuration(None, None)

        script_user = self._create_script_user("api_script")

        # Create a default user.
        with patch(
            "tank.authentication.ShotgunAuthenticator.get_default_user",
            return_value=script_user
        ):
            current_user = self._create_session_user("current_user")
            configuration._set_authenticated_user(
                current_user,
                sgtk.authentication.serialize_user(current_user)
            )

            self.assertEqual(id(sgtk.get_authenticated_user()), id(script_user))


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
