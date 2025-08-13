# Copyright (c) 2025 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.


import sys
import unittest

from sgtk_integration_test import SgtkIntegrationTest


class SGTKImportTests(SgtkIntegrationTest):
    """
    Validates that importing tank/sgtk does not load PySide/Qt modules.

    Run here because integration tests runs in standalone process
    """

    def test(self):
        print("test")
        self.assertIn("sgtk", sys.modules)
        self.assertNotIn("sgtk.authentication.ui.qt_abstraction", sys.modules)
        self.assertEqual(
            len([i for i in sys.modules if i.startswith("PySide")]),
            0,
        )


if __name__ == "__main__":
    unittest.main(failfast=True, verbosity=2)
