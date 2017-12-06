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
from tank.commands.setup_project import SetupProjectAction
from tank_vendor import yaml


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
        self.setup_fixtures(name="fixture_tests")
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

    # Core location is unimportant, as we won't copy it anyway, so mock out that functionality.
    @patch("sgtk.pipelineconfig_utils.get_path_to_current_core", return_value="/Users/jfboismenu/gitlocal/tk-core")
    @patch("sgtk.pipelineconfig_utils.resolve_all_os_paths_to_core", return_value={
        "linux2": "",
        "win32": "",
        "darwin": "",
    })
    @patch("sgtk.commands.core_localize.do_localize")
    def test_config_with_local_core(self, *_):

        project = self.mockgun.create("Project", {"name": "test_config_with_local_core"})

        s = SetupProjectAction()

        project_folder_name = "with_local_core"
        config_root = os.path.join(self.tank_temp, project_folder_name, "pipeline_configuration")

        os.makedirs(os.path.join(self.tank_temp, project_folder_name))

        s.run_noninteractive(
            logging.getLogger("test"),
            dict(
                config_uri=os.path.join(self.fixtures_root, "config"),
                project_id=project["id"],
                project_folder_name=project_folder_name,
                config_path_mac=config_root.replace("\\", "/"),
                config_path_win=config_root.replace("/", "\\"),
                config_path_linux=config_root.replace("\\", "/"),
                check_storage_path_exists=False
            )
        )

        tk = tank.sgtk_from_path(config_root)
        pc = tk.pipeline_configuration()
