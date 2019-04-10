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

import uuid
import os
import sys
from mock import patch

from tank_test.tank_test_base import setUpModule # noqa
from tank_test.tank_test_base import ShotgunTestBase, TankTestBase

from sgtk.bootstrap.cached_configuration import CachedConfiguration
from sgtk.bootstrap.configuration import Configuration
from sgtk.authentication import ShotgunAuthenticator, ShotgunSamlUser
from sgtk.authentication.user_impl import SessionUser
import sgtk
import tank_vendor
from tank_vendor import yaml

REPO_ROOT = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__), # <REPO_ROOT>/tests/bootstrap_tests
        "..",                      # <REPO_ROOT>/tests
        ".."                       # <REPO_ROOT>
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
        return ShotgunSamlUser(SessionUser(
            host="https://tank.shotgunstudio.com",
            login=name,
            session_token="session_token",
            http_proxy="http_proxy",
            session_metadata="session_metadata",
        ))

    def _create_script_user(self, api_script, host="https://test.shotgunstudio.com"):
        """
        Shorthand to create a script user.
        """
        return ShotgunAuthenticator().create_script_user(
            api_script, api_key=api_script[::-1], host=host
        )


class TestConfiguration(TestConfigurationBase):

    def test_login_to_login_authentication(self):
        """
        Ensure the configuration will always pick the user passed in when there is no script user
        in the project configuration.
        """
        default_user = self._create_session_user("default_user")

        configuration = Configuration(None, None)

        # Create a default user.
        with patch(
            "tank.authentication.ShotgunAuthenticator.get_default_user",
            return_value=default_user
        ):
            current_user = self._create_session_user("current_user")
            configuration._set_authenticated_user(
                current_user,
                current_user.login,
                sgtk.authentication.serialize_user(current_user)
            )

            # we should be using the same login...
            self.assertEqual(sgtk.get_authenticated_user().login, current_user.login)
            # ... but we shouldn't be using the name ShotgunUser instance. It should
            # have been serialized and deserialized.
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
                "tank_vendor.shotgun_authentication.deserialize_user",
                wraps=tank_vendor.shotgun_authentication.deserialize_user
            ) as deserialize_wrapper:
                current_user = self._create_session_user("current_user")
                configuration._set_authenticated_user(current_user, current_user.login, "invalid")

                deserialize_wrapper.assert_called_once_with("invalid")

                # Because we couldn't unserialize, we should just get the same login...
                self.assertEqual(sgtk.get_authenticated_user().login, current_user.login)
                # ... and the original ShotgunUser back.
                self.assertEqual(id(sgtk.get_authenticated_user()), id(current_user))

    def test_login_to_script_authentication(self):
        """
        Ensure the configuration will always pick the script user when project configuration has
        one.
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
                current_user.login,
                sgtk.authentication.serialize_user(current_user)
            )

            # The ShotgunUser instance from get_authenticated_user was retrieved
            # through get_default_user, so we simply need to compare the object ids.
            self.assertEqual(id(sgtk.get_authenticated_user()), id(script_user))

    def test_endpoint_url_swap(self):
        """
        Make sure that if the endpoint changes after the bootstrap that we're using the new endpoint.
        """
        configuration = Configuration(None, None)
        bootstrap_user = self._create_session_user("default_user")
        project_user = self._create_session_user("default_user", "https://test-2.shotgunstudio.com")

        with patch(
            "tank.authentication.ShotgunAuthenticator.get_default_user",
            return_value=project_user
        ):
            configuration._set_authenticated_user(
                bootstrap_user,
                bootstrap_user.login,
                sgtk.authentication.serialize_user(bootstrap_user)
            )

        self.assertEqual(sgtk.get_authenticated_user().host, "https://test-2.shotgunstudio.com")

    def test_script_to_script_authentication(self):
        """
        Ensure a project configuration overrides a script user used for bootstrapping.
        """
        configuration = Configuration(None, None)

        script_user_for_bootstrap = self._create_script_user("api_script_for_bootstrap")
        script_user_for_project = self._create_script_user("api_script_for_project")

        # Create a default user.
        with patch(
            "tank.authentication.ShotgunAuthenticator.get_default_user",
            return_value=script_user_for_project
        ):
            configuration._set_authenticated_user(
                script_user_for_bootstrap,
                script_user_for_bootstrap.login,
                sgtk.authentication.serialize_user(script_user_for_bootstrap)
            )

            # The ShotgunUser instance from get_authenticated_user was retrieved
            # through get_default_user, so we simply need to compare the object ids.
            self.assertEqual(id(sgtk.get_authenticated_user()), id(script_user_for_project))

    def test_script_to_noscript_authentication(self):
        """
        Ensure that bootstrapping with a script into a project without a script user in its
        configuration will pick the bootstrap user.
        """
        configuration = Configuration(None, None)

        user_for_bootstrap = self._create_script_user("api_script_for_bootstrap")
        user_for_project = self._create_session_user("project_user")

        # Create a default user.
        with patch(
            "tank.authentication.ShotgunAuthenticator.get_default_user",
            return_value=user_for_project
        ):
            configuration._set_authenticated_user(
                user_for_bootstrap,
                user_for_bootstrap.login,
                sgtk.authentication.serialize_user(user_for_bootstrap)
            )

            # we should be using the same login...
            auth_user = sgtk.get_authenticated_user()
            self.assertIsNone(auth_user.login)
            self.assertEqual(auth_user.login, user_for_bootstrap.login)
            self.assertEqual(auth_user.impl.get_script(), user_for_bootstrap.impl.get_script())
            # ... but we shouldn't be using the name ShotgunUser instance. It should
            # have been serialized and deserialized.
            self.assertNotEqual(id(auth_user), id(user_for_bootstrap))


class TestSSOClaims(TestConfigurationBase):

    def setUp(self):
        super(TestSSOClaims, self).setUp()

        config_folder = sgtk.util.ShotgunPath.from_current_os_path(
            os.path.join(self.tank_temp, str(uuid.uuid4()))
        )

        self._configuration = CachedConfiguration(
            config_folder,
            self.mockgun,
            sgtk.descriptor.create_descriptor(
                self.mockgun,
                sgtk.descriptor.Descriptor.CONFIG,
                "sgtk:descriptor:path?path={0}".format(self.fixtures_root)
            ),
            self.project["id"],
            "basic.dcc",
            None,
            []
        )

        self._mock_return_value(
            "tank.pipelineconfig_utils.get_core_python_path_for_config",
            return_value=os.path.join(REPO_ROOT, "python")
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
            return_value=None
        )
        self._stop_claims_mock = self._mock_return_value(
            "tank.authentication.user.ShotgunSamlUser.stop_claims_renewal",
            return_value=None
        )

    def test_claims_renewal_inactive(self):
        """
        Checks that is the claims renewal loop is not running it will not be restarted
        after core swap.
        """
        bootstrap_user = self._create_sso_user("bootstrap_user")
        project_user = self._create_sso_user("bootstrap_user")

        self._configuration.update_configuration()

        # Create a default user.
        with patch(
            "tank.authentication.ShotgunAuthenticator.get_default_user",
            return_value=project_user
        ):
            _, swapped_user = self._configuration.get_tk_instance(bootstrap_user)

        self.assertIsInstance(swapped_user, ShotgunSamlUser)
        self.assertEqual(self._start_claims_mock.called, False)
        self.assertEqual(self._stop_claims_mock.called, False)

    def test_claims_renewal_active(self):
        """
        Checks that claims renewal is stopped and restarted.
        """
        bootstrap_user = self._create_sso_user("bootstrap_user")
        project_user = self._create_sso_user("bootstrap_user")

        self._configuration.update_configuration()

        bootstrap_user.is_claims_renewal_active = lambda: True

        # Create a default user.
        with patch(
            "tank.authentication.ShotgunAuthenticator.get_default_user",
            return_value=project_user
        ):
            self.assertEqual(self._start_claims_mock.called, False)
            self.assertEqual(self._stop_claims_mock.called, False)
            _, swapped_user = self._configuration.get_tk_instance(bootstrap_user)

        self.assertIsInstance(swapped_user, ShotgunSamlUser)
        self.assertEqual(self._start_claims_mock.called, True)
        self.assertEqual(self._stop_claims_mock.called, True)

    def test_claims_to_script(self):
        """
        Checks that claims renewal is stopped and restarted.
        """
        bootstrap_user = self._create_sso_user("bootstrap_user")
        script_user = self._create_script_user("script_user")

        self._configuration.update_configuration()

        bootstrap_user.is_claims_renewal_active = lambda: True

        # Create a default user.
        with patch(
            "tank.authentication.ShotgunAuthenticator.get_default_user",
            return_value=script_user
        ):
            self.assertEqual(self._start_claims_mock.called, False)
            self.assertEqual(self._stop_claims_mock.called, False)
            _, swapped_user = self._configuration.get_tk_instance(bootstrap_user)

        self.assertEqual(self._stop_claims_mock.called, True)
        self.assertEqual(self._start_claims_mock.called, False)
        self.assertIsNone(swapped_user.login)


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
        # note: this is using the centralized config that is part of the
        #       std test fixtures.
        config = self._resolver.resolve_shotgun_configuration(
            self.sg_pc_entity["id"],
            "sgtk:descriptor:not?a=descriptor",
            self.mockgun,
            "john.smith"
        )
        self.assertIsInstance(
            config,
            sgtk.bootstrap.resolver.InstalledConfiguration
        )

        self.assertEqual(config.status(), config.LOCAL_CFG_UP_TO_DATE)

        # now get rid of some stuff from our fixtures to emulate
        # a config which was downloaded directly from github and not
        # created by setup_project
        os.remove(
            os.path.join(self.pipeline_config_root, "config", "core", "pipeline_configuration.yml")
        )

        os.remove(
            os.path.join(self.pipeline_config_root, "config", "core", "install_location.yml")
        )

        with self.assertRaisesRegex(
                sgtk.bootstrap.TankBootstrapError,
                "Cannot find required system file"):
            config.status()


class TestBakedConfiguration(TestConfigurationBase):
    def setUp(self):
        super(TestBakedConfiguration, self).setUp()
        self._tmp_bundle_cache = os.path.join(self.tank_temp, "bundle_cache")
        self._build_plugin_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "developer", "build_plugin.py")
        )
        sys.path.append(os.path.dirname(self._build_plugin_path))

    def tearDown(self):
        super(TestBakedConfiguration, self).tearDown()
        if os.path.dirname(self._build_plugin_path) in sys.path:
            sys.path.remove(os.path.dirname(self._build_plugin_path))
        # Tear down the running engine, if any
        current_engine = sgtk.platform.current_engine()
        if current_engine:
            current_engine.destroy()
        if sgtk.constants.ENV_VAR_EXTERNAL_PIPELINE_CONFIG_DATA in os.environ:
            del os.environ[sgtk.constants.ENV_VAR_EXTERNAL_PIPELINE_CONFIG_DATA]

    @patch("tank.authentication.ShotgunAuthenticator.get_user")
    @patch("sgtk.bootstrap.configuration_writer.ConfigurationWriter.install_core")
    @patch("sgtk.bootstrap.configuration_writer.ConfigurationWriter.create_tank_command")
    def test_build_and_use(self, core_install_mock, get_user_mock, create_tank_command_mock):
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
            self.mockgun,
            plugin_path,
            bake_folder,
            do_bake=True,
            use_system_core=True,
        )
        # And try to bootstrap it
        # The config name and version is controlled by the
        # fixtures/bootstrap_tests/test_plugin/info.yml file.
        bootstrap_script = os.path.join(bake_folder, "tk-config-boottest-v1.2.3", "bootstrap.py")
        # Define some globals needed by the bootstrap script
        global_namespace = {
            "__file__": bootstrap_script,
            "__name__": "__main__",
        }
        with open(bootstrap_script, "rb") as pf:
            exec(compile(pf.read(), bootstrap_script, "exec"), global_namespace)
        self.assertNotEqual(sgtk.platform.current_engine(), None)
        sgtk.platform.current_engine().destroy()


class TestCachedConfiguration(ShotgunTestBase):

    def setUp(self):
        super(TestCachedConfiguration, self).setUp()

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
                "sgtk:descriptor:path?path={0}".format(config_root)
            ),
            self.project["id"],
            "basic.*",
            None,
            []
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
        """
        Ensures that missing tank name on project is detected when using roots.
        """
        # Make sure that the missing tank name is detected.
        with self.assertRaises(sgtk.bootstrap.TankMissingTankNameError):
            self._cached_config.verify_required_shotgun_fields()

        # Ensure our change is backwards compatible.
        with self.assertRaises(sgtk.bootstrap.TankBootstrapError):
            self._cached_config.verify_required_shotgun_fields()

    def test_ensure_config_not_missing_after_update(self):
        """
        Ensures once a configuration is written that is ready.
        """
        self.assertEqual(self._cached_config.status(), self._cached_config.LOCAL_CFG_MISSING)
        self._cached_config.update_configuration()
        self.assertEqual(self._cached_config.status(), self._cached_config.LOCAL_CFG_UP_TO_DATE)

    def test_ensure_config_half_written_is_invalid(self):
        """
        Ensures a failure during bootstrap is detected and renders the configuration invalid.
        """
        self.assertEqual(self._cached_config.status(), self._cached_config.LOCAL_CFG_MISSING)
        # Force put the configuration in an inconsistent state.
        self._cached_config._config_writer.start_transaction()

        # Create the config folder so it isn't barely missing.
        os.makedirs(os.path.join(self._temp_config_root, "config"))

        self.assertEqual(self._cached_config.status(), self._cached_config.LOCAL_CFG_INVALID)

    def test_missing_deployment_file(self):
        """
        Ensures a missing deployment file results in an invalid config status.
        """
        self._cached_config.update_configuration()
        # Using a path descriptor will always give different.
        self.assertEqual(self._cached_config.status(), self._cached_config.LOCAL_CFG_UP_TO_DATE)
        os.remove(self._cached_config._config_writer.get_descriptor_metadata_file())
        self.assertEqual(self._cached_config.status(), self._cached_config.LOCAL_CFG_INVALID)

    def test_generation_number_mismatch(self):
        """
        Ensures a generation number mismatch will generate a different config status.
        """
        self._cached_config.update_configuration()
        # Using a path descriptor will always give different.
        self.assertEqual(self._cached_config.status(), self._cached_config.LOCAL_CFG_UP_TO_DATE)
        self._update_deploy_file(generation=9999999)
        self.assertEqual(self._cached_config.status(), self._cached_config.LOCAL_CFG_DIFFERENT)

    def test_different_descriptor(self):
        """
        Ensures a descriptor mismatch will generate a different config status.
        """
        self._cached_config.update_configuration()
        # Using a path descriptor will always give different.
        self.assertEqual(self._cached_config.status(), self._cached_config.LOCAL_CFG_UP_TO_DATE)
        self._update_deploy_file(descriptor={"type": "app_store", "name": "tk-config-basic", "version": "v1.0.0"})
        self.assertEqual(self._cached_config.status(), self._cached_config.LOCAL_CFG_DIFFERENT)

    def test_corrupted_file(self):
        """
        Ensures a corrupted deploy file will generates an invalid status.
        """
        self._cached_config.update_configuration()
        # Using a path descriptor will always give different.
        self.assertEqual(self._cached_config.status(), self._cached_config.LOCAL_CFG_UP_TO_DATE)
        self._update_deploy_file(corrupt=True)
        self.assertEqual(self._cached_config.status(), self._cached_config.LOCAL_CFG_INVALID)

    def test_mutable_descriptors(self):
        """
        Ensures a mutable descriptor will yield a different config status.
        """
        self._cached_config.update_configuration()
        self.assertEqual(self._cached_config.status(), self._cached_config.LOCAL_CFG_UP_TO_DATE)
        # Now force the descriptor to report that is is not immutable, the status will then be considered
        # as different since we can't assume everything has stayed the same.
        self._cached_config._descriptor.is_immutable = lambda: False
        self.assertEqual(self._cached_config.status(), self._cached_config.LOCAL_CFG_DIFFERENT)

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
                data = yaml.load(fh)
                if generation is not None:
                    data["deploy_generation"] = generation
                if descriptor is not None:
                    data["config_descriptor"] = descriptor

        with open(path, "wt") as fh:
            yaml.dump(data, fh)
