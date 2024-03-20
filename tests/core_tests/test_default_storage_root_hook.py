# Copyright (c) 2023 Autodesk.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

import tank
from tank import TankError

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    TankTestBase,
)


class TestDefaultStorageRootHook(TankTestBase):
    """
    Test the custom implementation of the default_storage_root hook
    which sets the default root to a project-specific root.
    """

    @mock.patch(
        "sgtk.pipelineconfig.PipelineConfiguration.get_core_hooks_location",
        return_value=os.path.join(
            os.path.dirname(__file__),
            "test_default_storage_root_hook/example1",
        ),
    )
    def test_roots_with_custom_project_field(self, *mocks):
        """
        Project-specific root is retrieved from custom Flow Production Tracking project field.
        """
        self.tk.shotgun.create("LocalStorage", {"code": "project_specific_root"})
        with mock.patch.object(
                self.tk.shotgun,
                "find_one",
                return_value={
                    "type": "Project",
                    "id": 1,
                    "sg_storage_root_name": "project_specific_root",
                },
        ):
            tk2 = tank.sgtk_from_path(self.project_root)
            self.assertEqual(
                tk2.pipeline_configuration.get_primary_data_root_name(),
                "project_specific_root",
            )

    @mock.patch(
        "sgtk.pipelineconfig.PipelineConfiguration.get_core_hooks_location",
        return_value=os.path.join(
            os.path.dirname(__file__),
            "test_default_storage_root_hook/example1",
        ),
    )
    def test_roots_with_invalid_storage_in_project_field(self, *mocks):
        """
        Local storage assigned to project in custom field isn't defined.
        Fall back to global root.
        """
        with mock.patch.object(
                self.tk.shotgun,
                "find_one",
                return_value={
                    "type": "Project",
                    "id": 1,
                    "sg_storage_root_name": "project_specific_root",
                },
        ):
            tk2 = tank.sgtk_from_path(self.project_root)
            self.assertEqual(
                tk2.pipeline_configuration.get_primary_data_root_name(),
                self.primary_root_name,
            )

    @mock.patch(
        "sgtk.pipelineconfig.PipelineConfiguration.get_core_hooks_location",
        return_value=os.path.join(
            os.path.dirname(__file__),
            "test_default_storage_root_hook/example1",
        ),
    )
    def test_roots_with_no_custom_project_field(self, *mocks):
        """
        Test fallback behaviour if no custom project field set.
        """
        tk2 = tank.sgtk_from_path(self.project_root)
        self.assertEqual(
            tk2.pipeline_configuration.get_primary_data_root_name(),
            self.primary_root_name,
        )

    @mock.patch(
        "sgtk.pipelineconfig.PipelineConfiguration.get_core_hooks_location",
        return_value=os.path.join(
            os.path.dirname(__file__),
            "test_default_storage_root_hook/example2",
        ),
    )
    def test_roots_with_environment_variable(self, *mocks):
        """
        Project-specific root is retrieved from environment variables.
        """
        with mock.patch.dict(
                os.environ,
                {
                    "STORAGE_ROOT_"
                    + str(
                        self.pipeline_configuration.get_project_id()
                    ): "project_specific_root"
                },
        ):
            tk2 = tank.sgtk_from_path(self.project_root)
            self.assertEqual(
                tk2.pipeline_configuration.get_primary_data_root_name(),
                "project_specific_root",
            )

    @mock.patch(
        "sgtk.pipelineconfig.PipelineConfiguration.get_core_hooks_location",
        return_value=os.path.join(
            os.path.dirname(__file__),
            "test_default_storage_root_hook/example2",
        ),
    )
    def test_roots_with_no_environment_variable(self, *mocks):
        """
        Test fallback behaviour if no environment variable set.
        """
        tk2 = tank.sgtk_from_path(self.project_root)
        self.assertEqual(
            tk2.pipeline_configuration.get_primary_data_root_name(),
            self.primary_root_name,
        )

    @mock.patch("sgtk.Sgtk.execute_core_hook_method", side_effect=TankError)
    def test_hook_exception(self, *mocks):
        """
        Test that raises an exception to pass code coverage.
        """
        tank.sgtk_from_path(self.project_root)

    @mock.patch(
        "sgtk.pipelineconfig.PipelineConfiguration.get_core_hooks_location",
        return_value=os.path.join(
            os.path.dirname(__file__),
            "test_default_storage_root_hook/example3",
        ),
    )
    def test_win_roots_with_custom_project_field(self, *mocks):
        """
        Project-specific windows root is retrieved from custom Flow Production Tracking project field.
        """
        self.tk.shotgun.create("LocalStorage", {"code": "primary_mapped",
                                                "windows_path": "P:\\Foo\\test_root", })

        with mock.patch.object(
                self.tk.shotgun,
                "find_one",
                return_value={
                    "type": "Project",
                    "id": 1,
                    "sg_projects_root": "P:\\Foo\\test_root",
                },
        ):
            tk2 = tank.sgtk_from_path(self.project_root)
            self.assertEqual(
                tk2.pipeline_configuration.get_primary_data_root_name(),
                "primary_mapped",
            )

    @mock.patch(
        "sgtk.pipelineconfig.PipelineConfiguration.get_core_hooks_location",
        return_value=os.path.join(
            os.path.dirname(__file__),
            "test_default_storage_root_hook/example3",
        ),
    )
    def test_win_roots_with_invalid_storage_in_project_field(self, *mocks):
        """
        Local storage assigned to project in custom field isn't defined.
        Fall back to global root.
        """
        with mock.patch.object(
                self.tk.shotgun,
                "find_one",
                return_value={
                    "type": "Project",
                    "id": 1,
                    "sg_projects_root": "P:\\Foo\\test_root",
                },
        ):
            tk2 = tank.sgtk_from_path(self.project_root)
            self.assertEqual(
                tk2.pipeline_configuration.get_primary_data_root_name(),
                self.primary_root_name,
            )

    @mock.patch(
        "sgtk.pipelineconfig.PipelineConfiguration.get_core_hooks_location",
        return_value=os.path.join(
            os.path.dirname(__file__),
            "test_default_storage_root_hook/example3",
        ),
    )
    def test_win_roots_with_no_custom_project_field(self, *mocks):
        """
        Test fallback behaviour if no custom project field set.
        """
        #
        self.tk.shotgun.create("LocalStorage", {"code": "primary_mapped", "windows_path": "P:\\Foo\\test_root"})
        tk2 = tank.sgtk_from_path(self.project_root)
        self.assertEqual(
            tk2.pipeline_configuration.get_primary_data_root_name(),
            self.primary_root_name,
        )
