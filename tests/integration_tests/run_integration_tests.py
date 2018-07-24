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
This script will run all the integration tests from this folder.
"""

from __future__ import print_function

import sys
import os
import glob


import subprocess


def main():

    current_folder, current_file = os.path.split(__file__)

    # Ensures code coverage will be generated
    coverage_path = os.path.normpath(
        os.path.join(current_folder, "..", "python", "third_party", "coverage")
    )

    filenames = glob.iglob(os.path.join(current_folder, "*.py"))
    for filename in filenames:

        # Skip the launcher. :)
        if filename.endswith(current_file):
            continue

        print("=" * 79)
        print("Running %s" % os.path.basename(filename))
        print("=" * 79)

        subprocess.check_call([
            sys.executable,
            coverage_path,
            "run",
            "-a",
            filename
        ])

        print()
        print()

if __name__ == "__main__":
    main()
