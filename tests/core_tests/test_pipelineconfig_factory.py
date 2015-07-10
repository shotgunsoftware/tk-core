# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from mock import patch

import sgtk
from tank_test.tank_test_base import *


class TestInit(TankTestBase):

    def setUp(self):
        super(TestInit, self).setUp()
        self.setup_fixtures()

    @patch("tank.api.Tank")
    @patch("tank.pipelineconfig_factory.PipelineConfiguration")
    @patch("tank.pipelineconfig_factory._get_pipeline_configuration_paths")
    @patch("tank.pipelineconfig_factory._get_configuration_context")
    @patch("tank.pipelineconfig_factory.__get_project_id")
    def test_sgtk_from_entity_with_mixed_slashes(
        self,
        get_project_id_mock,
        get_configuration_context_mock,
        get_pipeline_configuration_paths_mock,
        pipeline_configuration_mock,
        tank_mock
    ):
        """
        Makes sure that we can create a toolkit instance from paths that are messy with their
        slashes. We are mocking (especialy PipelineConfiguration and Tank) a lot of code to avoid
        needing an actual pipeline configuration or a live shotgun server. Mockgun was avoided because
        it would have made the test even bigger.
        """
        # Mock that there is a project
        get_project_id_mock.return_value = 1
        # Mock that TANK_CURRENT_PC is set.
        get_configuration_context_mock.return_value = "C:\\path\\to\\some\\configuration"
        # Mock that there are pipeline configurations and those have invalid slashes in them.
        get_pipeline_configuration_paths_mock.return_value = (["C:/path/to/some/configuration"], None)
        sgtk.sgtk_from_entity("Shot", 1234)
