#!/bin/bash
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
    export PIP=pip2.6
else
    export PIP=$1
fi

if [ -z "$2" ]; then
    export PYTHON=python2.6
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

from __future__ import print_function

import sys
sys.path.insert(0, 'third_party')

def main():
    # Ensures the ordereddict module was installed, which is required to run the tests on Python
    # 2.6
    try:
        import ordereddict
    except ImportError:
        print("Upgrade failed because 'ordereddict' could not be imported.")
        print("Please run this script from Python 2.6.")
        return

    # Ensures other modules required by the unit tests work!
    try:
        import mock
        import unittest2
        import coverage
        print("Upgrade successful!")
        print()
        print("Run 'git add third_party' to add changes made to the repo to the next commit.")
    except Exception as e:
        print("Upgrade failed! %s" % e)
main()