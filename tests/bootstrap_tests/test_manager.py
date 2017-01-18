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
