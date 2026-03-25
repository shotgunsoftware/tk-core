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
import subprocess  # nosec B404
import sys
import tempfile
import unittest

from sgtk_integration_test import SgtkIntegrationTest


class DeveloperScriptsTests(SgtkIntegrationTest):
    """Validate developer scripts work with pip sgtk installed.

    Creates a temporary venv with sgtk pip-installed, then runs each
    developer script from that venv to confirm they still prioritize
    the local tk-core (via sys.path.insert) over site-packages.
    """

    @classmethod
    def _get_venv_python(cls, venv_dir):
        """Return the path to the Python executable inside the venv."""
        if sys.platform == "win32":
            return os.path.join(venv_dir, "Scripts", "python.exe")
        return os.path.join(venv_dir, "bin", "python")

    @classmethod
    def setUpClass(cls):
        """Create a temp venv and install sgtk via pip."""
        super().setUpClass()
        cls._venv_dir = tempfile.mkdtemp(prefix="test_dev_scripts_")
        subprocess.check_call(  # nosec B603
            [sys.executable, "-m", "venv", cls._venv_dir]
        )
        cls._venv_python = cls._get_venv_python(cls._venv_dir)
        subprocess.check_call(  # nosec B603
            [cls._venv_python, "-m", "pip", "install", cls.tk_core_repo_root]
        )

    def test_bake_config(self):
        """Validate bake_config.py --help works."""
        script = os.path.join(self.tk_core_repo_root, "developer", "bake_config.py")
        subprocess.check_call([self._venv_python, script, "--help"])  # nosec B603

    def test_build_plugin(self):
        """Validate build_plugin.py --help works."""
        script = os.path.join(self.tk_core_repo_root, "developer", "build_plugin.py")
        subprocess.check_call([self._venv_python, script, "--help"])  # nosec B603

    def test_populate_bundle_cache(self):
        """Validate populate_bundle_cache.py --help works."""
        script = os.path.join(
            self.tk_core_repo_root, "developer", "populate_bundle_cache.py"
        )
        subprocess.check_call([self._venv_python, script, "--help"])  # nosec B603


if __name__ == "__main__":
    unittest.main(failfast=True, verbosity=2)
