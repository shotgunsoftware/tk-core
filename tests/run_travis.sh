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

if [[ $TRAVIS = true ]]; then
    # PySide is tricky to install and run. Let's get a wheel from someone who already compiled it for
    # Travis.
    # Taken from: https://stackoverflow.com/questions/24489588/how-can-i-install-pyside-on-travis
    sudo apt-get install libqt4-dev
    pip install PySide==1.2.2 --no-index --find-links https://parkin.github.io/python-wheelhouse/;
    # Travis CI servers use virtualenvs, so we need to finish the install by the following
    python ~/virtualenv/python${TRAVIS_PYTHON_VERSION}/bin/pyside_postinstall.py -install
    # Now we need to start the X server...
    # Taken from: https://github.com/colmap/colmap/commit/606d3cd09931d78a3272f99b5e7a2cb6894e243e
    export DISPLAY=:99.0
    sh -e /etc/init.d/xvfb start
    sleep 3
    # Finally, tell Qt to run offscreen.
    export QT_QPA_PLATFORM=offscreen
fi

# Insert the event type and python version, since we can be running multiple builds at the same time.
export SHOTGUN_TEST_ENTITY_SUFFIX="travis_${TRAVIS_EVENT_TYPE}_${TRAVIS_PYTHON_VERSION}"

# Do not launch the coverage for our unit tests with --with-coverage. If you do, run_tests will
# generate all the coverage in memory and not leave a .coverage file to be uploaded.
coverage run tests/run_tests.py


# Run these tests only if the integration tests environment variables are set.
if [ -z ${SHOTGUN_HOST+x} ]; then
    echo "Skipping integration tests, SHOTGUN_HOST is not set."
else
    python tests/integration_tests/run_integration_tests.py --with-coverage
fi