# Copyright 2026 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

"""
Validate that developer scripts work correctly even when sgtk is also
installed via pip in the same Python environment.

This ensures that developer scripts always use the local tk-core
(via sys.path.insert) and not the pip-installed version.
"""

import os
import subprocess
import sys
import unittest

from sgtk_integration_test import SgtkIntegrationTest


class DeveloperScriptsTests(SgtkIntegrationTest):
    """Validate developer scripts work with pip sgtk installed."""

    @classmethod
    def setUpClass(cls):
        """Install sgtk via pip to simulate the conflicting scenario."""
        super().setUpClass()
        subprocess.check_call(  # nosec B603
            [sys.executable, "-m", "pip", "install", cls.tk_core_repo_root]
        )

    def test_bake_config(self):
        """Validate bake_config.py --help works."""
        script = os.path.join(
            self.tk_core_repo_root, "developer", "bake_config.py"
        )
        subprocess.check_call(  # nosec B603
            [sys.executable, script, "--help"]
        )

    def test_build_plugin(self):
        """Validate build_plugin.py --help works."""
        script = os.path.join(
            self.tk_core_repo_root, "developer", "build_plugin.py"
        )
        subprocess.check_call(  # nosec B603
            [sys.executable, script, "--help"]
        )

    def test_populate_bundle_cache(self):
        """Validate populate_bundle_cache.py --help works."""
        script = os.path.join(
            self.tk_core_repo_root, "developer", "populate_bundle_cache.py"
        )
        subprocess.check_call(  # nosec B603
            [sys.executable, script, "--help"]
        )


if __name__ == "__main__":
    unittest.main(failfast=True, verbosity=2)
