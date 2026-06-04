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
        super().setUp()

        config_folder = sgtk.util.ShotgunPath.from_current_os_path(
            os.path.join(self.tank_temp, str(uuid.uuid4()))
        )

        self._configuration = CachedConfiguration(
            config_folder,
            self.mockgun,
            sgtk.descriptor.create_descriptor(
                self.mockgun,
                sgtk.descriptor.Descriptor.CONFIG,
                "sgtk:descriptor:path?path={0}".format(self.fixtures_root),
            ),
            self.project["id"],
            "basic.dcc",
            None,
            [],
        )

        self._mock_return_value(
            "tank.pipelineconfig_utils.get_core_python_path_for_config",
            return_value=os.path.join(REPO_ROOT, "python"),
        )

        # Do not waste time copying files around or core swapping. Also, deactivate
        # thread startup and shutdown, we only want to ensure they are invoked.
        for mocked_method in [
            "tank.bootstrap.import_handler.CoreImportHandler.swap_core",
            "tank.bootstrap.cached_configuration.CachedConfiguration._ensure_core_local",
            "tank.bootstrap.configuration_writer.ConfigurationWriter.install_core",
            "tank.bootstrap.configuration_writer.ConfigurationWriter.create_tank_command",
        ]:
            self._mock_return_value(mocked_method, return_value=None)

        self._start_claims_mock = self._mock_return_value(
            "tank.authentication.user.ShotgunSamlUser.start_claims_renewal",
            return_value=None,
        )
        self._stop_claims_mock = self._mock_return_value(
            "tank.authentication.user.ShotgunSamlUser.stop_claims_renewal",
            return_value=None,
        )

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
        super().setUp()
        self._tmp_bundle_cache = os.path.join(self.tank_temp, "bundle_cache")
        self._resolver = sgtk.bootstrap.resolver.ConfigurationResolver(
            plugin_id="tk-maya", bundle_cache_fallback_paths=[self._tmp_bundle_cache]
        )

    def test_resolve_installed_configuration(self):
        pass
class TestBakedConfiguration(TestConfigurationBase):
    def setUp(self):
        super().setUp()
        self._tmp_bundle_cache = os.path.join(self.tank_temp, "bundle_cache")
        self._build_plugin_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__), "..", "..", "developer", "build_plugin.py"
            )
        )
        sys.path.append(os.path.dirname(self._build_plugin_path))

    def tearDown(self):
        super().tearDown()
        if os.path.dirname(self._build_plugin_path) in sys.path:
            sys.path.remove(os.path.dirname(self._build_plugin_path))
        # Tear down the running engine, if any
        current_engine = sgtk.platform.current_engine()
        if current_engine:
            current_engine.destroy()
        if sgtk.constants.ENV_VAR_EXTERNAL_PIPELINE_CONFIG_DATA in os.environ:
            del os.environ[sgtk.constants.ENV_VAR_EXTERNAL_PIPELINE_CONFIG_DATA]

    @mock.patch("tank.authentication.ShotgunAuthenticator.get_user")
    @mock.patch("sgtk.bootstrap.configuration_writer.ConfigurationWriter.install_core")
    @mock.patch(
        "sgtk.bootstrap.configuration_writer.ConfigurationWriter.create_tank_command"
    )
    def test_build_and_use(
        self, core_install_mock, get_user_mock, create_tank_command_mock
    ):
        pass
class TestCachedConfiguration(ShotgunTestBase):
    def setUp(self):
        super().setUp()

        # Reset the tank_name and create a storage named after the one in the config.
        self.mockgun.update("Project", self.project["id"], {"tank_name": None})
        self.mockgun.create("LocalStorage", {"code": "primary"})

        # Initialize a cached configuration pointing to the config.
        config_root = os.path.join(self.fixtures_root, "bootstrap_tests", "config")

        self._temp_config_root = os.path.join(self.tank_temp, self.short_test_name)
        self._cached_config = CachedConfiguration(
            sgtk.util.ShotgunPath.from_current_os_path(self._temp_config_root),
            self.mockgun,
            sgtk.descriptor.create_descriptor(
                self.mockgun,
                sgtk.descriptor.Descriptor.CONFIG,
                "sgtk:descriptor:path?path={0}".format(config_root),
            ),
            self.project["id"],
            "basic.*",
            None,
            [],
        )

        # Due to this being a test that runs offline, we can't use anything other than a
        # path descriptor, which means that it is mutable. Because LOCAL_CFG_DIFFERENT
        # is actually returned by three different code paths, the only way to ensure that
        # we are indeed in the up to date state, which means everything is ready to do, is
        # to cheat and make the descriptor immutable by monkey-patching it.
        self._cached_config._descriptor.is_immutable = lambda: True
        # Seems up the test tremendously since installing core becomes a noop.
        self._cached_config._config_writer.install_core = lambda _: None
        self._cached_config._config_writer.create_tank_command = lambda: None

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
