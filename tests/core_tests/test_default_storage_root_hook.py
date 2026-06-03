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
        pass
    @mock.patch(
        "sgtk.pipelineconfig.PipelineConfiguration.get_core_hooks_location",
        return_value=os.path.join(
            os.path.dirname(__file__),
            "test_default_storage_root_hook/example1",
        ),
    )
    def test_roots_with_invalid_storage_in_project_field(self, *mocks):
        pass
    @mock.patch(
        "sgtk.pipelineconfig.PipelineConfiguration.get_core_hooks_location",
        return_value=os.path.join(
            os.path.dirname(__file__),
            "test_default_storage_root_hook/example1",
        ),
    )
    def test_roots_with_no_custom_project_field(self, *mocks):
        pass
    @mock.patch(
        "sgtk.pipelineconfig.PipelineConfiguration.get_core_hooks_location",
        return_value=os.path.join(
            os.path.dirname(__file__),
            "test_default_storage_root_hook/example2",
        ),
    )
    def test_roots_with_environment_variable(self, *mocks):
        pass
    @mock.patch(
        "sgtk.pipelineconfig.PipelineConfiguration.get_core_hooks_location",
        return_value=os.path.join(
            os.path.dirname(__file__),
            "test_default_storage_root_hook/example2",
        ),
    )
    def test_roots_with_no_environment_variable(self, *mocks):
        pass
    @mock.patch("sgtk.Sgtk.execute_core_hook_method", side_effect=TankError)
    def test_hook_exception(self, *mocks):
        pass
    @mock.patch(
        "sgtk.pipelineconfig.PipelineConfiguration.get_core_hooks_location",
        return_value=os.path.join(
            os.path.dirname(__file__),
            "test_default_storage_root_hook/example3",
        ),
    )
    def test_win_roots_with_custom_project_field(self, *mocks):
        pass
    @mock.patch(
        "sgtk.pipelineconfig.PipelineConfiguration.get_core_hooks_location",
        return_value=os.path.join(
            os.path.dirname(__file__),
            "test_default_storage_root_hook/example3",
        ),
    )
    def test_win_roots_with_invalid_storage_in_project_field(self, *mocks):
        pass
    @mock.patch(
        "sgtk.pipelineconfig.PipelineConfiguration.get_core_hooks_location",
        return_value=os.path.join(
            os.path.dirname(__file__),
            "test_default_storage_root_hook/example3",
        ),
    )
    def test_win_roots_with_no_custom_project_field(self, *mocks):
        pass
