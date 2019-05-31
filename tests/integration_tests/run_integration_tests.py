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

import time
import sys
import os
import glob
import copy


import subprocess


def main():

    current_folder = os.path.dirname(__file__)

    # Set up the environment variables so the test can be run simply by running
    # the test script.
    environ = copy.deepcopy(os.environ)
    environ["PYTHONPATH"] = os.path.pathsep.join([
        os.path.join(current_folder, "..", "python"),
        os.path.join(current_folder, "..", "python", "third_party"),
        os.path.join(current_folder, "..", "..", "python"),
    ])
    environ["SHOTGUN_SCRIPT_NAME"] = os.environ.get("SHOTGUN_SCRIPT_NAME")
    environ["SHOTGUN_SCRIPT_KEY"] = os.environ.get("SHOTGUN_SCRIPT_KEY")
    environ["SHOTGUN_HOST"] = os.environ.get("SHOTGUN_HOST")

    current_folder, current_file = os.path.split(__file__)

    before = time.time()
    try:
        filenames = glob.iglob(os.path.join(current_folder, "*.py"))
        for filename in filenames:

            # Skip the launcher. :)
            if filename.endswith(current_file):
                continue

            print("=" * 79)
            print("Running %s" % os.path.basename(filename))
            print("=" * 79)

            if "--with-coverage" in sys.argv:
                args = [
                    "coverage",
                    "run",
                    "-a",
                    filename
                ]
            else:
                args = [
                    sys.executable,
                    filename
                ]

            subprocess.check_call(args, env=environ)

            print()
            print()
    except Exception:
        print("=" * 79)
        print("Integration tests failed in %.2f" % (time.time() - before))
        raise
    else:
        print("=" * 79)
        print("Integration tests passed in %.2f" % (time.time() - before))


if __name__ == "__main__":
    main()
