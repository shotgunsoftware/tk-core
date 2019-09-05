# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
This test makes sure that various tank command operations do not fail.
"""

from __future__ import print_function

import traceback
import unittest2
from sgtk_integration_test import SgtkIntegrationTest
import sgtk

logger = sgtk.LogManager.get_logger(__name__)


class MultipleBootstrapAcrossCoreSwap(SgtkIntegrationTest):
    """
    Tests that it's possible to run bootstrap more than once.
    (Bug https://github.com/shotgunsoftware/tk-core/pull/643)

    This test will bootstrap into the project with an engine that doesn't exist
       - Core is swapped by bootstrap
       - TankMissingEngineError is raised
       - We catch it and attempt to launch an engine that does exist

    This is a subtle bug caused by the fact that the core swap may
    cause equality tests to fail. These can be reintroduced by local
    python imports so it's import to guard against these via tests.

    An innocent `isinstance()` or `except ExceptionClass` may end up
    returning the wrong thing because the core swap has swapped out
    the underlying classes but local imports have caused that the
    old code is still present in the system.
    """

    @classmethod
    def setUpClass(cls):
        """
        Sets up the test suite.
        """
        super(MultipleBootstrapAcrossCoreSwap, cls).setUpClass()

        # Create a sandbox project for this this suite to run under.
        cls.project = cls.create_or_find_project("MultipleBootstrapAcrossCoreSwap", {})

    def test_01_setup_legacy_bootstrap_core(self):
        """
        Test payload. See class docstring for details.
        """
        # Bootstrap into the tk-shell123 engine.
        manager = sgtk.bootstrap.ToolkitManager(self.user)
        manager.do_shotgun_config_lookup = False
        manager.base_configuration = "sgtk:descriptor:app_store?name=tk-config-basic"
        manager.caching_policy = sgtk.bootstrap.ToolkitManager.CACHE_SPARSE
        try:
            engine = manager.bootstrap_engine("tk-shell123", self.project)
        except Exception as e:
            traceback_str = traceback.format_exc()
            try:
                # First make sure we're getting the expected behaviour and the classes are not the same
                self.assertNotEqual(e.__class__, sgtk.platform.TankMissingEngineError)
                # Due to core swapping this comparison needs to happen by name
                self.assertEqual(e.__class__.__name__, sgtk.platform.TankMissingEngineError.__name__)
            except Exception:
                print("Error detected was:")
                print(traceback_str)
                raise
            engine = manager.bootstrap_engine("tk-shell", self.project)

        self.assertEqual(engine.name, "tk-shell")


if __name__ == "__main__":
    ret_val = unittest2.main(failfast=True, verbosity=2)
