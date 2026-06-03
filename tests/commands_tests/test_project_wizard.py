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

import datetime
import os
import sgtk

from sgtk.util import ShotgunPath


from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    TankTestBase,
)


class TestSetupProjectWizard(TankTestBase):
    """
    Makes sure environment code works with the app store mocker.
    """

    def setUp(self):
        pass
    def test_validate_config_uri(self):
        pass
    def test_set_project_disk_name(self):
        pass
    def test_preview_project_paths(self):
        pass
    def test_default_configuration_location_without_suggestions(self):
        pass
    def test_default_configuration_location_with_existing_pipeline_configuration(self):
        pass
    def test_get_core_settings(self):
        pass
    def test_execute(self):
        pass
