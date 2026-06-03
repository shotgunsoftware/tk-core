# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Unit tests tank setup_project.
"""

import os
import logging

import tank
from tank.util import is_linux, is_macos, is_windows
from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    TankTestBase,
)

from tank_test.mock_appstore import patch_app_store


class TestSetupProject(TankTestBase):
    """
    Tests related to a toolkit project setup
    """

    def setUp(self):
        pass
    @mock.patch("tank.pipelineconfig_utils.resolve_all_os_paths_to_core")
    def test_setup_centralized_project(self, mocked=None):
        pass
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.upload")
    @mock.patch("tank.pipelineconfig_utils.resolve_all_os_paths_to_core")
    def test_setup_distributed_project(
        pass
    ):
        """
        Test setting up a Project.
        """

        def mocked_resolve_core_path(core_path):
            return {"linux": core_path, "darwin": core_path, "win32": core_path}

        self.upload_associated_pipeline_config_id = None

        def mocked_upload(*args, **kwargs):
            # capture which pipeline config id we uploaded to
            self.upload_associated_pipeline_config_id = args[1]
            zip_file = args[2]
            self.assertTrue(zip_file.endswith("config.zip"))

        resolve_all_os_paths_to_core_mock.side_effect = mocked_resolve_core_path
        upload_mock.side_effect = mocked_upload

        # create new project
        new_project = {"type": "Project", "id": 1678, "name": "distributed_proj"}
        self.add_to_sg_mock_db(new_project)
        # location where the data will be installed
        os.makedirs(os.path.join(self.tank_temp, "distributed_proj"))

        command = self.tk.get_command("setup_project")
        command.set_logger(logging.getLogger("/dev/null"))
        # Test we can setup a new project and it does not fail.
        command.execute(
            {
                "project_id": new_project["id"],
                "project_folder_name": "distributed_proj",
                "install_mode": "distributed",
                "config_uri": self.project_config,
            }
        )

        # now test the expected outputs:
        # - pipeline configuration
        # - uploaded zip file
        data = self.mockgun.find(
            "PipelineConfiguration",
            [["project", "is", {"type": "Project", "id": new_project["id"]}]],
            [
                "code",
                "plugin_ids",
                "uploaded_config",
                "windows_path",
                "linux_path",
                "mac_path",
            ],
        )
        self.assertEqual(len(data), 1)
        pc_data = data[0]
        self.assertEqual(pc_data["type"], "PipelineConfiguration")
        self.assertEqual(pc_data["plugin_ids"], "basic.*")
        self.assertEqual(pc_data["code"], "Primary")
        self.assertEqual(pc_data["windows_path"], None)
        self.assertEqual(pc_data["linux_path"], None)
        self.assertEqual(pc_data["mac_path"], None)
        self.assertEqual(pc_data["id"], self.upload_associated_pipeline_config_id)

    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_install_location")
    @mock.patch("tank.pipelineconfig_utils.resolve_all_os_paths_to_core")
    def test_setup_project_with_external_core(
        pass
    ):
        """
        Test setting up a Project config that has a core/core_api.yml file included.
        """

        def mocked_resolve_core_path(core_path):
            return {"linux": core_path, "darwin": core_path, "win32": core_path}

        resolve_all_os_paths_to_core_mock.side_effect = mocked_resolve_core_path

        def mocked_get_install_location():
            return self._fake_core_install

        get_install_location_mock.side_effect = mocked_get_install_location

        # add a core_api.yml to our config that we are installing from, telling the
        # setup project command to use this when running the localize portion of the setup.
        core_api_path = os.path.join(self.project_config, "core", "core_api.yml")
        with open(core_api_path, "wt") as fp:
            fp.write("location:\n")
            fp.write("   type: dev\n")
            fp.write("   path: %s\n" % self.tank_source_path)

        try:
            # create new project
            new_project = {"type": "Project", "id": 1235, "name": "new_project_1235"}
            self.add_to_sg_mock_db(new_project)
            new_config_root = os.path.join(self.tank_temp, "new_project_1235_config")
            # location where the data will be installed
            os.makedirs(os.path.join(self.tank_temp, "new_project_1235"))

            command = self.tk.get_command("setup_project")
            command.set_logger(logging.getLogger("/dev/null"))
            # Test we can setup a new project and it does not fail.
            command.execute(
                {
                    "project_id": new_project["id"],
                    "project_folder_name": "new_project_1235",
                    "config_uri": self.project_config,
                    "config_path_mac": new_config_root if is_macos() else None,
                    "config_path_win": new_config_root if is_windows() else None,
                    "config_path_linux": new_config_root if is_linux() else None,
                }
            )

            # Check we get back our custom primary root name
            new_pc = tank.pipelineconfig_factory.from_path(new_config_root)
            self.assertEqual(
                list(new_pc.get_data_roots().keys()), ["setup_project_root"]
            )

            # the 'fake' core that we mocked earlier has a 'bad_path' folder
            self.assertFalse(
                os.path.exists(
                    os.path.join(new_config_root, "install", "core", "bad_path")
                )
            )

            # instead we expect a full installl
            self.assertTrue(
                os.path.exists(
                    os.path.join(
                        new_config_root,
                        "install",
                        "core",
                        "python",
                        "tank",
                        "errors.py",
                    )
                )
            )

        finally:
            os.remove(core_api_path)
