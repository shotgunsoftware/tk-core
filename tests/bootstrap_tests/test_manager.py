# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import with_statement

import sgtk
import os
from mock import patch, Mock

from sgtk.bootstrap import ToolkitManager

from tank_test.tank_test_base import setUpModule # noqa
from tank_test.tank_test_base import TankTestBase


class TestErrorHandling(TankTestBase):

    def test_get_pipeline_configurations_by_id(self):
        """
        Ensure that the resolver detects when an installed configuration has not been set for the
        current platform.
        """
        def find_mock_impl(*args, **kwargs):
            mgr = ToolkitManager()
            mgr.pipeline_configuration = 1
            with self.assertRaisesRegexp(
                sgtk.bootstrap.TankBootstrapError,
                "Can't enumerate pipeline configurations matching a specific id."
            ):
                mgr.get_pipeline_configurations(None)



class TestFunctionality(TankTestBase):

    @patch("tank.authentication.ShotgunAuthenticator.get_user", return_value=Mock())
    def test_sort_filter_configuration(self, _):
        mgr = ToolkitManager()
        project = dict(type="Project", id=1)

        # Empty entities in, empty entities out.
        self.assertEqual(
            mgr.sort_and_filter_configuration_entities(project, []),
            [],
        )

        # Filters out non-project configs.
        self.assertEqual(
            mgr.sort_and_filter_configuration_entities(
                project,
                [
                    dict(
                        type="PipelineConfiguration",
                        id=1,
                        code="Tester",
                        project=None,
                    ),
                ],
            ),
            [],
        )

        # Filters out configs from other projects.
        self.assertEqual(
            mgr.sort_and_filter_configuration_entities(
                project,
                [
                    dict(
                        type="PipelineConfiguration",
                        id=1,
                        code="Tester",
                        project=dict(type="Project", id=11),
                    ),
                ],
            ),
            [],
        )

        # Sorts the primary config first.
        primary_config = dict(
            code="Primary",
            project=project,
            id=2,
            type="PipelineConfiguration",
        )
        secondary_config = dict(
            code="Secondary",
            project=project,
            id=1,
            type="PipelineConfiguration",
        )
        # "code" becomes "name" in the output.
        output = [
            dict(name="Primary", project=project, id=2, type="PipelineConfiguration"),
            dict(name="Secondary", project=project, id=1, type="PipelineConfiguration"),
        ]
        self.assertEqual(
            mgr.sort_and_filter_configuration_entities(
                project,
                [secondary_config, primary_config],
            ),
            output,
        )

    @patch("tank.authentication.ShotgunAuthenticator.get_user", return_value=Mock())
    def test_pipeline_config_id_env_var(self, _):
        """
        Tests the SHOTGUN_PIPELINE_CONFIGURATION_ID being picked up at init
        """
        mgr = ToolkitManager()
        self.assertEqual(mgr.pipeline_configuration, None)

        os.environ["SHOTGUN_PIPELINE_CONFIGURATION_ID"] = "123"
        try:
            mgr = ToolkitManager()
            self.assertEqual(mgr.pipeline_configuration, 123)
        finally:
            del os.environ["SHOTGUN_PIPELINE_CONFIGURATION_ID"]

        os.environ["SHOTGUN_PIPELINE_CONFIGURATION_ID"] = "invalid"
        try:
            mgr = ToolkitManager()
            self.assertEqual(mgr.pipeline_configuration, None)
        finally:
            del os.environ["SHOTGUN_PIPELINE_CONFIGURATION_ID"]

    @patch("tank.authentication.ShotgunAuthenticator.get_user", return_value=Mock())
    def test_get_entity_from_environment(self, _):

        # no env set
        mgr = ToolkitManager()
        self.assertEqual(mgr.get_entity_from_environment(), None)

        # std case
        os.environ["SHOTGUN_ENTITY_TYPE"] = "Shot"
        os.environ["SHOTGUN_ENTITY_ID"] = "123"
        try:
            self.assertEqual(
                mgr.get_entity_from_environment(),
                {"type": "Shot", "id": 123}
            )
        finally:
            del os.environ["SHOTGUN_ENTITY_TYPE"]
            del os.environ["SHOTGUN_ENTITY_ID"]

        # site mismatch
        os.environ["SHOTGUN_SITE"] = "https://some.other.site"
        os.environ["SHOTGUN_ENTITY_TYPE"] = "Shot"
        os.environ["SHOTGUN_ENTITY_ID"] = "123"
        try:
            self.assertEqual(
                mgr.get_entity_from_environment(),
                None
            )
        finally:
            del os.environ["SHOTGUN_ENTITY_TYPE"]
            del os.environ["SHOTGUN_ENTITY_ID"]
            del os.environ["SHOTGUN_SITE"]

        # invalid data case
        os.environ["SHOTGUN_ENTITY_TYPE"] = "Shot"
        os.environ["SHOTGUN_ENTITY_ID"] = "invalid"
        try:
            self.assertEqual(
                mgr.get_entity_from_environment(),
                None
            )
        finally:
            del os.environ["SHOTGUN_ENTITY_TYPE"]
            del os.environ["SHOTGUN_ENTITY_ID"]
