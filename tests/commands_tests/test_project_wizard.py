# Copyright (c) 2019 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Unit tests tank updates.
"""

from __future__ import with_statement

import datetime
import os
import sgtk
from mock import patch

from sgtk.util import ShotgunPath

from tank_test.tank_test_base import TankTestBase
from tank_test.tank_test_base import setUpModule  # noqa


class TestSetupProjectWizard(TankTestBase):
    """
    Makes sure environment code works with the app store mocker.
    """

    def setUp(self):
        """
        Prepare unit test.
        """
        super(TestSetupProjectWizard, self).setUp(
            parameters={"primary_root_name": "primary"}
        )
        self._wizard = sgtk.get_command("setup_project_factory").execute({})

        self._storage_locations = ShotgunPath(
            "Z:\\projects", "/mnt/projects", "/Volumes/projects"
        )
        self._storage_locations.current_os = self.tank_temp

        self.mockgun.update(
            "LocalStorage",
            self.primary_storage["id"],
            self._storage_locations.as_shotgun_dict(),
        )

        # Prepare the wizard for business. All these methods are actually passing
        # information directly to the SetupProjectParams object inside
        # the wizard, so there's no need to test them per-se.
        self._wizard.set_project(self.project["id"], force=True)
        self._wizard.set_use_distributed_mode()

        self.config_uri = os.path.join(self.fixtures_root, "config")
        self._wizard.set_config_uri(self.config_uri)

    def test_validate_config_uri(self):
        """
        Ensure that we can validate the URI.

        This doesn't actually test much, it is simply there as a proof that
        there is a bug in the API right now. We should get back to this in the
        future.
        """
        storage_setup = self._wizard.validate_config_uri(self.config_uri)

        expected_primary_storage = {
            "default": True,
            "defined_in_shotgun": True,
            "description": "Default location where project data is stored.",
            "exists_on_disk": True,
            "shotgun_id": self.primary_storage["id"],
            # FIXME: This is a bug. The StorageRoots instance, owned by the SetupProjectParams,
            # is initialized to these values by default. They are then injected into
            # the result of validate_config_uri. validate_config_uri is expected
            # however to return paths named after sys.platform and not <os>_path.
            # We can review this once the Python 3 port is done.
            "linux_path": "/studio/projects",
            "mac_path": "/studio/projects",
            "windows_path": "\\\\network\\projects",
        }
        # Inject the storage locations we set on the local storage earlier.
        expected_primary_storage.update(self._storage_locations.as_system_dict())
        self.assertEqual(storage_setup, {"primary": expected_primary_storage})

    def test_set_project_disk_name(self):
        """
        Ensure the project folder gets created or not on demand.
        """
        # Make sure the config we have is valid.
        project_locations = self._storage_locations.join(self.short_test_name)

        self._wizard.set_project_disk_name(self.short_test_name, False)
        self.assertFalse(os.path.exists(project_locations.current_os))
        self._wizard.set_project_disk_name(self.short_test_name, True)
        self.assertTrue(os.path.exists(project_locations.current_os))

    def test_preview_project_paths(self):
        """
        Ensure all project paths get returned properly.
        """
        self.assertEqual(
            self._wizard.preview_project_paths(self.short_test_name),
            {
                "primary": self._storage_locations.join(
                    self.short_test_name
                ).as_system_dict()
            },
        )

    def test_default_configuration_location_without_suggestions(self):
        """
        Ensure that when no matching pipeline configurations are found that
        we do not get a suggestion back.
        """
        self._wizard.set_project_disk_name(self.short_test_name)
        locations = self._wizard.get_default_configuration_location()
        self.assertEqual(locations, {"win32": None, "darwin": None, "linux2": None})

    def test_default_configuration_location_with_existing_pipeline_configuration(self):
        """
        Ensure that when the tank_name and the configuration folder name are the same
        for the latest configuration found in Shotgun, we'll offer a pre-baked path
        to the user using the new project name.

        For e.g., if a project with a tank_name set to "potato" and whose configuration
        was written to "/vegatables/potato", then a new project with tank name "radish"
        would get a default location of "/vegatables/radish".
        """
        self._wizard.set_project_disk_name(self.short_test_name)

        # Create a project with a tank name matching the name of the folder for the pipeline configuration
        other_project = self.mockgun.create(
            "Project", {"name": "Other Project", "tank_name": "other_project"}
        )
        self.mockgun.create(
            "PipelineConfiguration",
            {
                "code": "primary",
                "created_at": datetime.datetime.now(),
                "project": other_project,
                "mac_path": "/Volumes/configs/other_project",
                "linux_path": "/mnt/configs/other_project",
                "windows_path": "Z:\\configs\\other_project",
            },
        )

        locations = self._wizard.get_default_configuration_location()
        self.assertEqual(
            locations,
            {
                "darwin": "/Volumes/configs/{0}".format(self.short_test_name),
                "linux2": "/mnt/configs/{0}".format(self.short_test_name),
                "win32": "Z:\\configs\\{0}".format(self.short_test_name),
            },
        )

    def test_get_core_settings(self):
        """
        Ensure we can find the core settings. Given this is a unit test and not
        running off a real core, there's nothing more we can do at the moment.
        """
        # Core is installed as
        # <studio-install>/install/core/python
        # This file is under the equivalent of
        # <studio-install>/install/core/tests/commands_tests/test_project_wizard.py
        # So we have to pop 4 folders to get back the equivalent location.
        install_location = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
        )
        self.assertEqual(
            self._wizard.get_core_settings(),
            {
                "core_path": ShotgunPath.from_current_os_path(
                    install_location
                ).as_system_dict(),
                "localize": True,
                "pipeline_config": None,
                "using_runtime": True,
            },
        )

    def test_execute(self):
        """
        Ensure we can set up the project.
        """
        self._wizard.set_project_disk_name(self.short_test_name)
        path = ShotgunPath.from_current_os_path(
            os.path.join(self.tank_temp, self.short_test_name, "pipeline")
        )
        self._wizard.set_configuration_location(path.linux, path.windows, path.macosx)

        # Upload method not implemented on Mockgun yet, so skip that bit.
        with patch("tank_vendor.shotgun_api3.lib.mockgun.mockgun.Shotgun.upload"):
            with patch("tank.pipelineconfig_utils.get_core_api_version") as api_mock:
                api_mock.return_value = "HEAD"
                self._wizard.execute()
