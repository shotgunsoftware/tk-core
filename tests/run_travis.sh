#!/usr/bin/env bash
# Copyright (c) 2017 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

#
# This file is run by the travis builds. It will ensure all sources can be compiled and all tests
# pass. If the SHOTGUN_COMPILE_ONLY environment variable is set, tests will not be run.
#

set -e

python -m compileall python/tank
python -m compileall tests/*.py
python -m compileall tests/*/*.py

if [[ $SHOTGUN_COMPILE_ONLY -eq 1 ]]; then
    exit 0
fi


if [[ $TRAVIS -eq 1 ]]; then
    # PySide is tricky to install and run. Let's get a wheel from someone who already compiled it for
    # Travis.
    sudo apt-get install libqt4-dev
    pip install PySide==1.2.2 --no-index --find-links https://parkin.github.io/python-wheelhouse/;
    # Travis CI servers use virtualenvs, so we need to finish the install by the following
    python ~/virtualenv/python${TRAVIS_PYTHON_VERSION}/bin/pyside_postinstall.py -install
    # Now we need to start the X server...
    export DISPLAY=:99.0
    sh -e /etc/init.d/xvfb start
    sleep 3
fi


PYTHONPATH=tests/python/third_party python -3 tests/python/third_party/coverage run tests/run_tests.py
