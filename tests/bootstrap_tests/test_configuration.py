# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import uuid
import os
import sys

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
    TankTestBase,
)

from tank.bootstrap import constants
from sgtk.bootstrap.cached_configuration import CachedConfiguration
from sgtk.bootstrap.configuration import Configuration
from sgtk.authentication import ShotgunAuthenticator, ShotgunSamlUser
from sgtk.authentication.user_impl import SessionUser
import sgtk
import tank_vendor
from tank_vendor import yaml

REPO_ROOT = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),  # <REPO_ROOT>/tests/bootstrap_tests
        "..",  # <REPO_ROOT>/tests
        "..",  # <REPO_ROOT>
    )
)


class TestConfigurationBase(ShotgunTestBase):
    def _create_session_user(self, name, host="https://test.shotgunstudio.com"):
        """
        Shorthand to create a session user.
        """
        return ShotgunAuthenticator().create_session_user(
            name, session_token=name[::-1], host=host
        )

    def _create_sso_user(self, name):
        return ShotgunSamlUser(
            SessionUser(
                host="https://tank.shotgunstudio.com",
                login=name,
                session_token="session_token",
                http_proxy="http_proxy",
                session_metadata="session_metadata",
            )
        )

    def _create_script_user(self, api_script, host="https://test.shotgunstudio.com"):
        """
        Shorthand to create a script user.
        """
        return ShotgunAuthenticator().create_script_user(
            api_script, api_key=api_script[::-1], host=host
        )


class TestConfiguration(TestConfigurationBase):
    def test_login_to_login_authentication(self):
        pass
    def test_fail_reinstantiating(self):
        pass
    def test_login_to_script_authentication(self):
        pass
    def test_endpoint_url_swap(self):
        pass
    def test_script_to_script_authentication(self):
        pass
    def test_script_to_noscript_authentication(self):
        pass
class TestSSOClaims(TestConfigurationBase):
    def setUp(self):
        pass
    def test_claims_renewal_inactive(self):
        pass
    def test_claims_renewal_active(self):
        pass
    def test_claims_to_script(self):
        pass
class TestInvalidInstalledConfiguration(TankTestBase):
    """
    Tests that error messages are raised at startup when
    the linux/windows/path fields are set to a configuration which
    isn't valid
    """

    def setUp(self):
        pass
    def test_resolve_installed_configuration(self):
        pass
class TestBakedConfiguration(TestConfigurationBase):
    def setUp(self):
        pass
    def tearDown(self):
        pass
    @mock.patch("tank.authentication.ShotgunAuthenticator.get_user")
    @mock.patch("sgtk.bootstrap.configuration_writer.ConfigurationWriter.install_core")
    @mock.patch(
        "sgtk.bootstrap.configuration_writer.ConfigurationWriter.create_tank_command"
    )
    def test_build_and_use(
        pass
    ):
        """
        Test baking a plugin and bootstrapping it with current tk-core.
        """
        default_user = self._create_session_user("default_user")
        get_user_mock.return_value = default_user
        # Bake the plugin
        import build_plugin

        plugin_path = os.path.join(self.fixtures_root, "bootstrap_tests", "test_plugin")
        bake_folder = os.path.join(self.tank_temp, "test_baked")
        build_plugin.build_plugin(
            self.mockgun, plugin_path, bake_folder, do_bake=True, use_system_core=True
        )
        # And try to bootstrap it
        # The config name and version is controlled by the
        # fixtures/bootstrap_tests/test_plugin/info.yml file.
        bootstrap_script = os.path.join(
            bake_folder, "tk-config-boottest-v1.2.3", "bootstrap.py"
        )
        # Define some globals needed by the bootstrap script
        global_namespace = {"__file__": bootstrap_script, "__name__": "__main__"}
        with open(bootstrap_script, "rb") as pf:
            exec(compile(pf.read(), bootstrap_script, "exec"), global_namespace)
        self.assertNotEqual(sgtk.platform.current_engine(), None)
        sgtk.platform.current_engine().destroy()


class TestCachedConfiguration(ShotgunTestBase):
    def setUp(self):
        pass
    def test_verifies_tank_name(self):
        pass
    def test_ensure_config_not_missing_after_update(self):
        pass
    def test_ensure_config_half_written_is_invalid(self):
        pass
    def test_missing_deployment_file(self):
        pass
    def test_generation_number_mismatch(self):
        pass
    def test_different_descriptor(self):
        pass
    def test_corrupted_file(self):
        pass
    def test_mutable_descriptors(self):
        pass
    def _update_deploy_file(self, generation=None, descriptor=None, corrupt=False):
        """
        Updates the deploy file.

        :param generation: If set, will update the generation number of the config.
        :param descriptor: If set, will update the descriptor of the config.
        :param corrupt: If set, will corrupt the configuration file.
        """
        path = self._cached_config._config_writer.get_descriptor_metadata_file()
        if corrupt:
            data = "corrupted"
        else:
            with open(path, "rt") as fh:
                data = yaml.load(fh, Loader=yaml.FullLoader)
                if generation is not None:
                    data["deploy_generation"] = generation
                if descriptor is not None:
                    data["config_descriptor"] = descriptor

        with open(path, "wt") as fh:
            yaml.dump(data, fh)
