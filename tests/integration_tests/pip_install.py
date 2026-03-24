# Copyright 2025 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

"""
Validate that sgtk can be installed via pip in a clean virtual environment
and that all tank_vendor imports resolve correctly.

This script creates a temporary venv, runs pip install, and verifies
that critical imports work without the pkgs.zip vendored dependencies.
"""

import os
import subprocess
import sys
import tempfile
import unittest

from sgtk_integration_test import SgtkIntegrationTest


class PipInstallTests(SgtkIntegrationTest):
    """Validate pip install and tank_vendor imports in a clean venv."""

    @classmethod
    def _get_venv_python(cls, venv_dir):
        """Return the path to the Python executable inside the venv."""
        if sys.platform == "win32":
            return os.path.join(venv_dir, "Scripts", "python.exe")
        return os.path.join(venv_dir, "bin", "python")

    def test_pip_install_and_import(self):
        """Validate pip install followed by import sgtk in a clean venv."""
        tk_core_root = self.tk_core_repo_root

        with tempfile.TemporaryDirectory(prefix="test_pip_") as venv_dir:
            subprocess.check_call(  # nosec B603
                [sys.executable, "-m", "venv", venv_dir]
            )
            python = self._get_venv_python(venv_dir)

            subprocess.check_call(  # nosec B603
                [python, "-m", "pip", "install", tk_core_root]
            )
            subprocess.check_call(  # nosec B603
                [python, "-c", "import sgtk"]
            )
            subprocess.check_call(  # nosec B603
                [python, "-c", "from tank_vendor.shotgun_api3 import Shotgun"]
            )
            subprocess.check_call(  # nosec B603
                [python, "-c", "from tank_vendor import yaml"]
            )
            subprocess.check_call(  # nosec B603
                [
                    python,
                    "-c",
                    "from tank_vendor.shotgun_api3.lib import httplib2",
                ]
            )


if __name__ == "__main__":
    unittest.main(failfast=True, verbosity=2)
