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
from __future__ import with_statement

import os
import sys
import logging

import tank
from tank_test.tank_test_base import TankTestBase, setUpModule # noqa

from tank_test.mock_appstore import patch_app_store
from mock import patch


class TestSetupProject(TankTestBase):
    """
    Tests related to a toolkit project setup
    """

    def setUp(self):
        """
        Prepare unit test.
        """
        TankTestBase.setUp(
            self,
            # Use a custom primary root name
            parameters={"primary_root_name": "setup_project_root"}
        )
        self.setup_fixtures("app_store_tests")

        patcher = patch_app_store()
        self._mock_store = patcher.start()
        self.addCleanup(patcher.stop)

        # Make sure we have a version in the app store for all bundles.
        self._mock_store.add_engine("tk-engine", "v1.0.0")
        self._mock_store.add_engine("tk-test", "v1.0.0")
        self._mock_store.add_application("tk-multi-app", "v1.0.0")
        self._mock_store.add_application("tk-multi-nodep", "v1.0.0")
        self._mock_store.add_framework("tk-framework-test", "v1.0.0")
        self._mock_store.add_framework("tk-framework-2nd-level-dep", "v1.0.0")

        # the std fixtures do not have a full core installation so ensure
        # that we mock one that localize can pick up
        self._fake_core_install = os.path.join(self.tank_temp, "fake_core_install")
        if not os.path.exists(self._fake_core_install):
            os.makedirs(os.path.join(self._fake_core_install, "install"))
            os.makedirs(os.path.join(self._fake_core_install, "install", "core"))
            os.makedirs(os.path.join(self._fake_core_install, "install", "core", "fake_core"))
            os.makedirs(os.path.join(self._fake_core_install, "config"))
            cfg_core = os.path.join(self._fake_core_install, "config", "core")
            os.makedirs(cfg_core)
            self.create_file(os.path.join(cfg_core, "shotgun.yml"), "{host: http://unit_test_mock_sg}")
            self.create_file(os.path.join(cfg_core, "interpreter_Darwin.cfg"), "")
            self.create_file(os.path.join(cfg_core, "interpreter_Linux.cfg"), "")
            self.create_file(os.path.join(cfg_core, "interpreter_Windows.cfg"), "")


    @patch("tank.pipelineconfig_utils.resolve_all_os_paths_to_core")
    def test_setup_centralized_project(self, mocked=None):
        """
        Test setting up a Project.
        """
        def mocked_resolve_core_path(core_path):
            return {
                "linux2": core_path,
                "darwin": core_path,
                "win32": core_path,
            }
        mocked.side_effect = mocked_resolve_core_path

        # create new project
        new_project = {
            "type": "Project",
            "id": 1234,
            "code": "new_project_1234",
        }
        self.add_to_sg_mock_db(new_project)
        # location where the config will be installed
        new_config_root = os.path.join(self.tank_temp, "new_project_1234_config")
        # location where the data will be installed
        os.makedirs(os.path.join(self.tank_temp, "new_project_1234"))

        command = self.tk.get_command("setup_project")
        command.set_logger(logging.getLogger("/dev/null"))
        # Test we can setup a new project and it does not fail.
        command.execute({
            "project_id": new_project["id"],
            "project_folder_name": "new_project_1234",
            "config_uri": self.project_config,
            "config_path_mac": new_config_root if sys.platform == "darwin" else None,
            "config_path_win": new_config_root if sys.platform == "win32" else None,
            "config_path_linux": new_config_root if sys.platform.startswith("linux") else None,
        })

        # Check we get back our custom primary root name
        new_pc = tank.pipelineconfig_factory.from_path(new_config_root)
        self.assertEqual(new_pc.get_data_roots().keys(), ["setup_project_root"])

        # make sure the fake core didn't get copied across, e.g. that
        # we didn't localize the setup
        self.assertFalse(os.path.exists(
            os.path.join(new_config_root, "install", "core", "bad_path")
        ))

        # make sure we have the core location files for this unlocalized setup
        self.assertTrue(os.path.exists(
            os.path.join(new_config_root, "install", "core", "core_Darwin.cfg")
        ))

    @patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.upload")
    @patch("tank.pipelineconfig_utils.resolve_all_os_paths_to_core")
    def test_setup_distributed_project(self, resolve_all_os_paths_to_core_mock, upload_mock):
        """
        Test setting up a Project.
        """
        def mocked_resolve_core_path(core_path):
            return {
                "linux2": core_path,
                "darwin": core_path,
                "win32": core_path,
            }

        self.upload_associated_pipeline_config_id = None

        def mocked_upload(*args, **kwargs):
            # capture which pipeline config id we uploaded to
            self.upload_associated_pipeline_config_id = args[1]
            zip_file = args[2]
            self.assertTrue(zip_file.endswith("config.zip"))

        resolve_all_os_paths_to_core_mock.side_effect = mocked_resolve_core_path
        upload_mock.side_effect = mocked_upload

        # create new project
        new_project = {
            "type": "Project",
            "id": 1678,
            "code": "distributed_proj",
        }
        self.add_to_sg_mock_db(new_project)
        # location where the data will be installed
        os.makedirs(os.path.join(self.tank_temp, "distributed_proj"))

        command = self.tk.get_command("setup_project")
        command.set_logger(logging.getLogger("/dev/null"))
        # Test we can setup a new project and it does not fail.
        command.execute({
            "project_id": new_project["id"],
            "project_folder_name": "distributed_proj",
            "install_mode": "distributed",
            "config_uri": self.project_config,
        })

        # now test the expected outputs:
        # - pipeline configuration
        # - uploaded zip file
        data = self.mockgun.find(
            "PipelineConfiguration",
            [["project", "is", {"type": "Project", "id": new_project["id"]}]],
            ["code", "plugin_ids", "uploaded_config", "windows_path", "linux_path", "mac_path"]
        )
        self.assertEquals(len(data), 1)
        pc_data = data[0]
        self.assertEquals(pc_data["type"], "PipelineConfiguration")
        self.assertEquals(pc_data["plugin_ids"], "basic.*")
        self.assertEquals(pc_data["code"], "Primary")
        self.assertEquals(pc_data["windows_path"], None)
        self.assertEquals(pc_data["linux_path"], None)
        self.assertEquals(pc_data["mac_path"], None)
        self.assertEquals(pc_data["id"], self.upload_associated_pipeline_config_id)

    @patch("tank.pipelineconfig.PipelineConfiguration.get_install_location")
    @patch("tank.pipelineconfig_utils.resolve_all_os_paths_to_core")
    def test_setup_project_with_external_core(self, resolve_all_os_paths_to_core_mock, get_install_location_mock):
        """
        Test setting up a Project config that has a core/core_api.yml file included.
        """
        def mocked_resolve_core_path(core_path):
            return {
                "linux2": core_path,
                "darwin": core_path,
                "win32": core_path,
            }
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
            new_project = {
                "type": "Project",
                "id": 1235,
                "code": "new_project_1235",
            }
            self.add_to_sg_mock_db(new_project)
            new_config_root = os.path.join(self.tank_temp, "new_project_1235_config")
            # location where the data will be installed
            os.makedirs(os.path.join(self.tank_temp, "new_project_1235"))

            command = self.tk.get_command("setup_project")
            command.set_logger(logging.getLogger("/dev/null"))
            # Test we can setup a new project and it does not fail.
            command.execute({
                "project_id": new_project["id"],
                "project_folder_name": "new_project_1235",
                "config_uri": self.project_config,
                "config_path_mac": new_config_root if sys.platform == "darwin" else None,
                "config_path_win": new_config_root if sys.platform == "win32" else None,
                "config_path_linux": new_config_root if sys.platform.startswith("linux") else None,
            })

            # Check we get back our custom primary root name
            new_pc = tank.pipelineconfig_factory.from_path(new_config_root)
            self.assertEqual(new_pc.get_data_roots().keys(), ["setup_project_root"])

            # the 'fake' core that we mocked earlier has a 'bad_path' folder
            self.assertFalse(os.path.exists(
                os.path.join(new_config_root, "install", "core", "bad_path")
            ))

            # instead we expect a full installl
            self.assertTrue(os.path.exists(
                os.path.join(new_config_root, "install", "core", "python", "tank", "errors.py")
            ))

        finally:
            os.remove(core_api_path)


