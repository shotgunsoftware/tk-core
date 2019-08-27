# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys
import logging

from mock import patch

from tank_test.tank_test_base import setUpModule # noqa
from tank_test.tank_test_base import TankTestBase, temp_env_var

import tank
from tank.commands import get_command
from tank.bootstrap.configuration_writer import ConfigurationWriter
from tank.descriptor import Descriptor, create_descriptor
from tank_vendor import yaml
from tank.util import ShotgunPath


class TestPipelineConfig(TankTestBase):
    """
    Tests for the pipeline configuration.
    """

    def test_read_env_var_in_pipeline_configuration_yaml(self):
        """
        Ensures environment variables are properly translated.
        """
        self._test_read_env_var_in_pipeline_configuration_yml(
            "env_var_pipeline",
            {
                "project_name": "$SGTK_TEST_PROJECT_NAME",
                "project_id": "$SGTK_TEST_PROJECT_ID",
                "pc_id": "$SGTK_TEST_PC_ID",
                "pc_name": "$SGTK_TEST_PC_NAME"
            }
        )
        if sys.platform == "win32":
            self._test_read_env_var_in_pipeline_configuration_yml(
                "env_var_pipeline_windows",
                {
                    "project_name": "%SGTK_TEST_PROJECT_NAME%",
                    "project_id": "%SGTK_TEST_PROJECT_ID%",
                    "pc_id": "%SGTK_TEST_PC_ID%",
                    "pc_name": "%SGTK_TEST_PC_NAME%"
                }
            )

    def _test_read_env_var_in_pipeline_configuration_yml(self, folder_name, pipeline_config_data):
        """
        Ensures environment variables are properly translated for a given file format.

        :param folder_name: Name of the configuration to create on disk.
        :param pipeline_config_data: Data to insert into shotgun.yml
        """
        env_var_pipeline = os.path.join(
            self.tank_temp, folder_name
        )
        core_folder = os.path.join(env_var_pipeline, "config", "core")
        pipeline_configuration_yml_path = os.path.join(
            core_folder, "pipeline_configuration.yml"
        )

        os.makedirs(core_folder)

        with open(pipeline_configuration_yml_path, "w") as fh:
            yaml.safe_dump(pipeline_config_data, fh)

        with open(os.path.join(core_folder, "roots.yml"), "w") as fh:
            fh.write("{}")

        test_project_name = "test_project_name"
        test_project_id = 12345
        test_pc_id = 67890
        test_pc_name = "test_pc_name"
        # tank.pipeline_config is actually a local variable inside tank/__init__.py,
        # so get the class from somewhere else...

        with temp_env_var(
            SGTK_TEST_PROJECT_NAME=test_project_name,
            SGTK_TEST_PROJECT_ID=str(test_project_id),
            SGTK_TEST_PC_ID=str(test_pc_id),
            SGTK_TEST_PC_NAME=test_pc_name
        ):
            pc = tank.pipelineconfig_factory.PipelineConfiguration(
                env_var_pipeline
            )

        self.assertEqual(
            pc.get_name(),
            test_pc_name
        )

        self.assertEqual(
            pc.get_shotgun_id(),
            test_pc_id
        )

        self.assertEqual(
            pc.get_project_id(),
            test_project_id
        )

        self.assertEqual(
            pc.get_project_disk_name(),
            test_project_name
        )

    def test_update_metadata(self):
        """
        Tests if updating the pipeline to site config actually updates it.
        """
        self.assertFalse(self.tk.pipeline_configuration.is_site_configuration())

        # Make sure the project has been concerted to a site config.
        self.tk.pipeline_configuration.convert_to_site_config()
        self.assertTrue(self.tk.pipeline_configuration.is_site_configuration())

        # Make sure that the setting was correctly written to disk by recreating
        # another instance of the pipeline configuration object so that it reloads
        # it from disk.
        tk2 = tank.sgtk_from_path(self.tk.pipeline_configuration.get_path())
        self.assertTrue(tk2.pipeline_configuration.is_site_configuration())

    def test_default_pipeline_in_unittest(self):
        """
        Make sure that we are using the default pipeline configuration from
        the unit tests.
        """
        self.assertEqual(
            self.tk.pipeline_configuration.get_published_file_entity_type(),
            "PublishedFile"
        )

    def test_fixture_pipeline_reloaded(self):
        """
        Makes sure we are using the pipeline configuration form the fixture
        """
        # The fixture contains a pipeline_configuration.yml file that needs to be copied into the
        # pipeline_configuration_root, so we'll copy the configuration into it.
        self.setup_fixtures(name="fixture_tests", parameters={"installed_config": True})
        self.assertEqual(
            self.tk.pipeline_configuration.get_shotgun_id(),
            42
        )
        self.assertEqual(
            self.tk.pipeline_configuration.get_project_id(),
            42
        )
        self.assertEqual(
            self.tk.pipeline_configuration.get_project_disk_name(),
            "abc"
        )
        self.assertEqual(
            self.tk.pipeline_configuration.get_name(),
            "Firstary"
        )


class TestConfigLocations(TankTestBase):
    """
    Ensures pipeline configurations report their folders at the right location.
    """

    def setUp(self):
        super(TestConfigLocations, self).setUp({"primary_root_name": "primary"})
        self._project = self.mockgun.create("Project", {"name": "config_locations_test"})

    def test_token_resolution_with_installed_configuration(self):
        """
        Tests an installed configuration's resolving of the CONFIG_FOLDER and PIPELINE_CONFIG
        """
        self.setup_fixtures(parameters={"installed_config": True})

        # For path and the platform specific path token...
        for path_key in ["path", ShotgunPath.get_shotgun_storage_key()]:
            # For both path based descriptors..
            for desc_type in ["path", "dev"]:
                # For both tokens that can point to the bunldes that have been copied inside the
                # pipeline configuration...
                for desc_str in [
                    "sgtk:descriptor:%s?%s={PIPELINE_CONFIG}/config/bundles/test_app" % (desc_type, path_key),
                    "sgtk:descriptor:%s?%s={CONFIG_FOLDER}/bundles/test_app" % (desc_type, path_key)
                ]:
                    desc = self.tk.pipeline_configuration.get_app_descriptor(desc_str)
                    # Ensure the bundle is resolved inside the installed configuration.
                    self.assertEqual(
                        desc.get_path(), os.path.join(self.pipeline_config_root, "config", "bundles", "test_app")
                    )

    def test_token_resolution_with_cached_configuration(self):
        """
        Tests a cached configuration's resolving of the CONFIG_FOLDER
        """
        self.setup_fixtures()

        # For path and the platform specific path token...
        for path_key in ["path", ShotgunPath.get_shotgun_storage_key()]:
            # For both path based descriptors...
            for desc_type in ["path", "dev"]:
                desc_str = "sgtk:descriptor:%s?%s={CONFIG_FOLDER}/bundles/test_app" % (desc_type, path_key)
                desc = self.tk.pipeline_configuration.get_app_descriptor(desc_str)
                # Ensure the bundle is resolved inside the source configuration.
                self.assertEqual(
                    desc.get_path(), os.path.join(self.fixtures_root, "config", "bundles", "test_app")
                )

    def test_classic_config_with_studio_core(self):
        """
        Tests the paths for a classic configuration with a studio core.
        """
        pc, config_root, core_root = self._setup_project(is_localized=False)
        self._test_core_locations(pc, core_root, is_localized=False)
        self._test_config_locations(pc, config_root, os.path.join(config_root, "config"))

    def test_classic_config_with_local_core(self):
        """
        Tests the paths for a classic configuration with a localized core.
        """
        pc, config_root, core_root = self._setup_project(is_localized=True)
        self._test_core_locations(pc, config_root, is_localized=True)
        self._test_config_locations(pc, config_root, os.path.join(config_root, "config"))

    def test_zero_config(self):
        """
        Tests the paths for a zero-config configuration.
        """
        config_root = os.path.join(self.tank_temp, "zero_config")

        config_desc = create_descriptor(
            self.mockgun,
            Descriptor.CONFIG,
            "sgtk:descriptor:path?path=%s" % os.path.join(self.fixtures_root, "config")
        )
        cw = ConfigurationWriter(
            tank.util.ShotgunPath.from_current_os_path(config_root),
            self.mockgun
        )

        cw.ensure_project_scaffold()
        config_desc.copy(os.path.join(config_root, "config"))
        cw.write_pipeline_config_file(None, self._project["id"], "basic", [], config_desc)
        cw.update_roots_file(config_desc)
        cw.write_install_location_file()

        # Fake a core installation.
        core_install_folder = os.path.join(config_root, "install", "core")
        self.create_file(os.path.join(core_install_folder, "_core_upgrader.py"))
        self.assertTrue(tank.pipelineconfig_utils.is_localized(config_root))

        pc = tank.pipelineconfig.PipelineConfiguration(config_root)

        self._test_core_locations(pc, config_root, True)
        self._test_config_locations(pc, config_root, config_desc.get_path())

    def _setup_project(self, is_localized):
        """
        Setups a Toolkit classic pipeline configuration with a localized or not core.
        """

        # Create the project's destination folder.
        locality = "localized" if is_localized else "studio"
        project_folder_name = "config_with_%s_core" % locality
        config_root = os.path.join(self.tank_temp, project_folder_name, "pipeline_configuration")

        os.makedirs(os.path.join(self.tank_temp, project_folder_name))

        # Mock a core that will setup the project.
        core_root = os.path.join(self.tank_temp, "%s_core" % locality)
        core_install_folder = os.path.join(core_root, "install", "core")
        os.makedirs(core_install_folder)

        # Mock a localized core if required.
        if is_localized:
            self.create_file(os.path.join(core_root, "config", "core", "interpreter_Darwin.cfg"))
            self.create_file(os.path.join(core_root, "config", "core", "interpreter_Windows.cfg"))
            self.create_file(os.path.join(core_root, "config", "core", "interpreter_Linux.cfg"))
            self.create_file(os.path.join(core_root, "config", "core", "shotgun.yml"))
            self.create_file(os.path.join(core_root, "config", "core", "roots.yml"))
            self.create_file(os.path.join(core_install_folder, "_core_upgrader.py"))
            self.assertEqual(tank.pipelineconfig_utils.is_localized(core_root), True)

        # We have to patch these methods because the core doesn't actually exist on disk for the tests.
        with patch("sgtk.pipelineconfig_utils.get_path_to_current_core", return_value=core_root):
            with patch("sgtk.pipelineconfig_utils.resolve_all_os_paths_to_core", return_value={
                "linux2": core_root if sys.platform == "linux2" else None,
                "win32": core_root if sys.platform == "win32" else None,
                "darwin": core_root if sys.platform == "darwin" else None
            }):
                command = get_command("setup_project", self.tk)
                command.set_logger(logging.getLogger("test"))
                command.execute(
                    dict(
                        config_uri=os.path.join(self.fixtures_root, "config"),
                        project_id=self._project["id"],
                        project_folder_name=project_folder_name,
                        config_path_mac=config_root if sys.platform == "darwin" else None,
                        config_path_win=config_root if sys.platform == "win32" else None,
                        config_path_linux=config_root if sys.platform == "linux2" else None,
                        check_storage_path_exists=False,
                    )
                )

        tk = tank.sgtk_from_path(config_root)
        pc = tk.pipeline_configuration

        return pc, config_root, core_root

    def _test_core_locations(self, pc, expected_core_root, is_localized):
        """
        Test locations that are reported by the core,
        """
        # Core location tests.
        self.assertEqual(pc.is_localized(), is_localized)
        self.assertEqual(pc.get_install_location(), expected_core_root)
        self.assertEqual(
            pc.get_core_python_location(),
            os.path.join(expected_core_root, "install", "core", "python")
        )

    def _test_config_locations(self, pc, autogen_files_root, config_files_root):
        """
        Test locations that are reported by the configuration.
        """
        # Pipeline configuration location tests.
        self.assertEqual(pc.get_path(), autogen_files_root)
        self.assertEqual(
            pc._get_yaml_cache_location(),
            os.path.join(autogen_files_root, "yaml_cache.pickle")
        )
        self.assertEqual(
            pc._get_pipeline_config_file_location(),
            os.path.join(autogen_files_root, "config", "core", "pipeline_configuration.yml")
        )
        self.assertEqual(
            pc._storage_roots.roots_file,
            os.path.join(autogen_files_root, "config", "core", "roots.yml")
        )
        self.assertEqual(
            pc.get_all_os_paths(),
            tank.util.ShotgunPath(
                autogen_files_root if sys.platform == "win32" else None,
                autogen_files_root if sys.platform == "linux2" else None,
                autogen_files_root if sys.platform == "darwin" else None
            )
        )

        # Config folder location test.
        self.assertEqual(
            pc.get_config_location(),
            os.path.join(config_files_root))
        self.assertEqual(
            pc.get_core_hooks_location(),
            os.path.join(config_files_root, "core", "hooks")
        )
        self.assertEqual(
            pc.get_schema_config_location(),
            os.path.join(config_files_root, "core", "schema")
        )
        self.assertEqual(
            pc.get_hooks_location(),
            os.path.join(config_files_root, "hooks")
        )
        self.assertEqual(
            pc.get_shotgun_menu_cache_location(),
            os.path.join(autogen_files_root, "cache")
        )
        self.assertEqual(
            pc.get_environment_path("test"),
            os.path.join(config_files_root, "env", "test.yml")
        )
        self.assertEqual(
            pc._get_templates_config_location(),
            os.path.join(config_files_root, "core", "templates.yml")
        )
