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
    Makes sure environment code works with the app store mocker.
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
        self.second_project = {
            "type": "Project",
            "id": 7777,
            "code": "another_project",
        }
        self.add_to_sg_mock_db(self.second_project)
        project_root = os.path.join(self.tank_temp, "test_setup_project")
        os.makedirs(project_root)

        # Make sure we have a version in the app store for all bundles.
        self._mock_store.add_engine("tk-engine", "v1.0.0")
        self._mock_store.add_engine("tk-test", "v1.0.0")
        self._mock_store.add_application("tk-multi-app", "v1.0.0")
        self._mock_store.add_application("tk-multi-nodep", "v1.0.0")
        self._mock_store.add_framework("tk-framework-test", "v1.0.0")
        self._mock_store.add_framework("tk-framework-2nd-level-dep", "v1.0.0")

    @patch("tank.pipelineconfig_utils.resolve_all_os_paths_to_core")
    def test_setup_project(self, mocked=None):
        """
        Test setting up a Project.
        """
        new_config_root = os.path.join(self.tank_temp, "test_setup_project_%s" % "config")

        def mocked_resolve_core_path(core_path):
            return {
                "linux2": core_path,
                "darwin": core_path,
                "win32": core_path,
            }

        mocked.side_effect = mocked_resolve_core_path
        command = self.tk.get_command("setup_project")
        command.set_logger(logging.getLogger("/dev/null"))
        # Test we can setup a new project and it does not fail.
        command.execute({
            "project_id": self.second_project["id"],
            "project_folder_name": "test_setup_project",
            "config_uri": self.project_config,
            "config_path_mac": new_config_root if sys.platform == "darwin" else None,
            "config_path_win": new_config_root if sys.platform == "win32" else None,
            "config_path_linux": new_config_root if sys.platform.startswith("linux") else None,
        })
        new_pc = tank.pipelineconfig_factory.from_path(new_config_root)
        # Check we get back our custom primary root name
        self.assertEqual(new_pc.get_data_roots().keys(), ["setup_project_root"])
