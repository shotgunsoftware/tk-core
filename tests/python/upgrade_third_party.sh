#!/bin/bash -e
# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

# Read pip and python location from the command-line or use defaults.
if [ -z "$1" ]; then
    export PIP=pip3
else
    export PIP=$1
fi

if [ -z "$2" ]; then
    export PYTHON=python3
else
    export PYTHON=$2
fi

echo "Removing all existing third party libraries from the repo."
echo "=========================================================="
rm -rf third_party
echo "Done!"

echo
echo "Installing all third party libraries into 'third_party' folder."
echo "==============================================================="
echo Launching $PIP
$PIP install -r requirements.txt -t third_party

echo
echo "Testing installed libraries"
echo "==========================="
echo Launching $PYTHON
$PYTHON - <<EOF

import sys
sys.path.insert(0, 'third_party')

import importlib

def main():
    # Ensures other modules required by the unit tests work!
    try:
        for mod_name in [
            "mock",
            "coverage",
        ]:
            mod_imported = importlib.import_module(mod_name)
            if not mod_imported.__file__.startswith("third_party/"):
                raise Exception(f"Require to run in a Python environment not having the {mod_name} already installed")

        print("Upgrade successful!")
        print()
        print("Run 'git add third_party' to add changes made to the repo to the next commit.")
    except Exception as e:
        print("Upgrade failed! %s" % e)
        sys.exit(1)
main()