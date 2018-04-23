# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
This test makes sure that various tank command operations do not fail.
"""

from __future__ import print_function

import os
import sys
import unittest2
from mock import Mock, patch
from sgtk_integration_test import SgtkIntegrationTest
import sgtk

logger = sgtk.LogManager.get_logger(__name__)


class MultipleBootstrapAcrossCoreSwap(SgtkIntegrationTest):
    """
    Tests that it's possible to run bootstrap more than once.
    (Bug https://github.com/shotgunsoftware/tk-core/pull/643)

    This test will:

    1. Set up a basic core
    2. Run setup_project from the core to set up a new project
    3. Bootstrap into the project with an engine that doesn't exist
       - Core is swapped by bootstrap
       - TankMissingEngineError is raised
       - We catch it and attempt to launch an engine that does exist

    This is a subtle bug caused by the fact that the core swap may
    cause equality tests to fail. These can be reintroduced by local
    python imports so it's import to guard against these via tests.

    An innocent `isinstance()` or `except ExceptionClass` may end up
    returning the wrong thing because the core swap has swapped out
    the underlying classes but local imports have caused that the
    old code is still present in the system.
    """

    @classmethod
    def setUpClass(cls):
        """
        Sets up the test suite.
        """
        super(MultipleBootstrapAcrossCoreSwap, cls).setUpClass()

        cls.installed_config_location = os.path.join(cls.temp_dir, "config")

        # Create a sandbox project for this this suite to run under.
        cls.project = cls.create_or_find_project("MultipleBootstrapAcrossCoreSwap", {})

    def _create_basic_install(self, path):
        """
        Creates a basic toolkit install that we can run setup_project from.
        :param str path: Path to where install should be placed.
        """
        cw = sgtk.bootstrap.configuration_writer.ConfigurationWriter(
            sgtk.util.ShotgunPath.from_current_os_path(path),
            self.sg
        )

        # Activate the core.
        cw.ensure_project_scaffold()

        install_core_folder = os.path.join(path, "install", "core")
        os.makedirs(install_core_folder)

        cw.write_shotgun_file(Mock(get_path=lambda: "does_not_exist"))
        cw.write_install_location_file()

        sgtk.util.filesystem.copy_folder(
            self.tk_core_repo_root,
            install_core_folder,
            skip_list=[".git", "docs", "tests"]
        )
        cw.create_tank_command()

    def test_01_setup_legacy_bootstrap_core(self):
        """
        Test payload. See class docstring for details.
        """
        if sys.platform == "darwin":
            path_param = "config_path_mac"
        elif sys.platform == "win32":
            path_param = "config_path_win"
        elif sys.platform.startswith("linux"):
            path_param = "config_path_linux"

        # create a basic install that we can run setup_project from
        install_location = os.path.join(self.temp_dir, "preflight_install")
        self._create_basic_install(install_location)

        # Now run setup_project for the basic config
        params = {
            "config_uri": "tk-config-basic",
            "force": True,
            "project_folder_name": "bootstrap_test",
            "project_id": self.project["id"],
            path_param: self.installed_config_location,
        }
        setup_project = sgtk.get_command("setup_project")
        setup_project.set_logger(logger)
        sgtk.set_authenticated_user(self.user)

        with patch(
            "tank.pipelineconfig_utils.resolve_all_os_paths_to_core",
            return_value=sgtk.util.ShotgunPath.from_current_os_path(
                install_location
            ).as_system_dict()
        ):
            setup_project.execute(params)

        # Find the project and pipeline configuration in Shotgun.
        project = self.sg.find_one("Project", [["id", "is", self.project["id"]]])
        pc = self.sg.find_one("PipelineConfiguration", [["code", "is", "Primary"], ["project", "is", project]])

        # Bootstrap into the tk-shell123 engine.
        manager = sgtk.bootstrap.ToolkitManager(self.user)
        manager.pipeline_configuration = pc["id"]
        try:
            engine = manager.bootstrap_engine("tk-shell123", project)
        except Exception as e:
            # note: due to core swapping this comparison needs to happen by name
            self.assertEqual(e.__class__.__name__, sgtk.platform.TankMissingEngineError.__name__)
            engine = manager.bootstrap_engine("tk-shell", project)

        self.assertEqual(engine.name, "tk-shell")


if __name__ == "__main__":
    ret_val = unittest2.main(failfast=True, verbosity=2)
