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
Unit tests tank validate.
"""

from __future__ import with_statement

import logging

from tank_test.tank_test_base import TankTestBase, setUpModule # noqa

from tank_test.mock_appstore import patch_app_store


class TestSimpleValidate(TankTestBase):
    """
    Makes sure environment code works with the app store mocker.
    """

    def setUp(self):
        """
        Prepare unit test.
        """
        TankTestBase.setUp(self)

        patcher = patch_app_store()
        self._mock_store = patcher.start()
        self.addCleanup(patcher.stop)

        # Test is running validate on the configuration files, so we'll copy the config into the
        # pipeline configuration.
        self.setup_fixtures("app_store_tests", parameters={"installed_config": True})

        self._mock_store.add_engine("tk-test", "v1.0.0")
        self._mock_store.add_application("tk-multi-nodep", "v1.0.0")
        self._mock_store.add_application("tk-multi-nodep", "v2.0.0")
        self._mock_store.add_framework("tk-framework-test", "v1.0.0")
        self._mock_store.add_framework("tk-framework-test", "v1.0.1")
        self._mock_store.add_framework("tk-framework-test", "v1.1.0")

    def test_simple_validate(self):
        """
        Test Simple validate.
        Makes sure that the command runs without an error in a simple environment.
        """
        # Run validate.
        command = self.tk.get_command("validate")
        command.set_logger(logging.getLogger("/dev/null"))
        command.execute({"envs": ["simple"]})