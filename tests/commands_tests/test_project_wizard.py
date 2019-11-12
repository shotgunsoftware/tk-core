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
Unit tests tank updates.
"""

from __future__ import with_statement

import datetime
import os
import sgtk
import logging
from pprint import pprint
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

        self._logs = []

        def set_progress_callback(msg, percentage):
            self._logs.append((msg, percentage))

        # We're going to setup a project on disk.
        self._wizard.set_progress_callback(set_progress_callback)
        self._wizard.set_project(self.project["id"], force=True)
        self._wizard.set_use_centralized_mode()

        self.config_uri = os.path.join(self.fixtures_root, "config")
        self._wizard.set_config_uri(self.config_uri)

        self._logs = []

    def test_validate_config_uri(self):
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
            "linux_path": "/studio/projects",
            "mac_path": "/studio/projects",
            "windows_path": "\\\\network\\projects",
        }
        # Inject the storage locations we set on the local storage earlier.
        expected_primary_storage.update(self._storage_locations.as_system_dict())
        self.assertEqual(storage_setup, {"primary": expected_primary_storage})

    def test_set_project_disk_name(self):
        """
        Ensure the command works.
        """
        # Make sure the config we have is valid.
        project_locations = self._storage_locations.join(self.short_test_name)

        self._wizard.set_project_disk_name(self.short_test_name, False)
        self.assertFalse(os.path.exists(project_locations.current_os))
        self._wizard.set_project_disk_name(self.short_test_name, True)
        self.assertTrue(os.path.exists(project_locations.current_os))

    def test_preview_project_paths(self):
        print(self._wizard.preview_project_paths(self.short_test_name))

        self.assertEqual(
            self._wizard.preview_project_paths(self.short_test_name),
            {
                "primary": self._storage_locations.join(
                    self.short_test_name
                ).as_system_dict()
            },
        )

    def test_default_configuration_location_without_suggestions(self):
        self._wizard.set_project_disk_name(self.short_test_name)
        locations = self._wizard.get_default_configuration_location()
        self.assertEqual(locations, {"win32": None, "darwin": None, "linux2": None})

    def test_default_configuration_location_with_existing_pipeline_configuration(self):
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
