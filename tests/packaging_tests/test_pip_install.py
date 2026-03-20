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


def get_venv_python(venv_dir):
    """Return the path to the Python executable inside the venv."""
    if sys.platform == "win32":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python")


def main():
    tk_core_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))

    with tempfile.TemporaryDirectory(prefix="test_pip_") as venv_dir:
        print("Creating clean venv in %s" % venv_dir)
        subprocess.check_call([sys.executable, "-m", "venv", venv_dir])

        python = get_venv_python(venv_dir)

        print("Installing sgtk via pip...")
        subprocess.check_call(
            [python, "-m", "pip", "install", tk_core_root],
        )

        print("Validating import sgtk...")
        subprocess.check_call([python, "-c", "import sgtk"])

        print("Validating tank_vendor.shotgun_api3...")
        subprocess.check_call(
            [python, "-c", "from tank_vendor.shotgun_api3 import Shotgun"]
        )

        print("Validating tank_vendor.yaml...")
        subprocess.check_call([python, "-c", "from tank_vendor import yaml"])

        print("Validating tank_vendor.shotgun_api3.lib.httplib2...")
        subprocess.check_call(
            [
                python,
                "-c",
                "from tank_vendor.shotgun_api3.lib import httplib2",
            ]
        )

    print("All pip install validations passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
