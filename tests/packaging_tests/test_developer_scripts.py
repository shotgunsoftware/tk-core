# Copyright 2025 Autodesk, Inc.  All rights reserved.
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


def main():
    tk_core_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
    developer_dir = os.path.join(tk_core_root, "developer")

    # First, install sgtk via pip to simulate the conflicting scenario
    print("Installing sgtk via pip to simulate conflict...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", tk_core_root],
    )

    scripts = [
        "bake_config.py",
        "build_plugin.py",
        "populate_bundle_cache.py",
    ]

    for script in scripts:
        script_path = os.path.join(developer_dir, script)
        print("Validating %s --help..." % script)
        subprocess.check_call(
            [sys.executable, script_path, "--help"],
        )

    print("All developer script validations passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
