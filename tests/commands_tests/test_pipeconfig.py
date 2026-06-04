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
Unit tests tank pipeline configs.
"""

import os
import tempfile
import shutil
import stat

import sgtk
from tank.errors import TankError
from tank.util import is_windows

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    TankTestBase,
)

from tank_test.mock_appstore import patch_app_store


class TestPipelineConfig(TankTestBase):
    """
    Perform tests around pipeline configs
    """

    def setUp(self):
        """
        Prepare unit test.
        """
        TankTestBase.setUp(self)

        patcher = patch_app_store()
        self._mock_store = patcher.start()
        self.addCleanup(patcher.stop)

    def test_pc_push(self):
        pass
