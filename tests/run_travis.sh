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

if [[ $TRAVIS = true ]]; then

    if [[ $QT_TEST_VER = 4 ]]; then
        # PySide is tricky to install and run. Let's get a wheel from someone who already compiled it for
        # Travis.
        # Taken from: https://stackoverflow.com/questions/24489588/how-can-i-install-pyside-on-travis
        sudo apt-get install libqt4-dev
        pip install PySide==1.2.2 --no-index --find-links https://parkin.github.io/python-wheelhouse/;
        # Travis CI servers use virtualenvs, so we need to finish the install by the following
        python ~/virtualenv/python${TRAVIS_PYTHON_VERSION}/bin/pyside_postinstall.py -install
    elif [[ $QT_TEST_VER = 5 ]]; then
        pip install PySide2==5.13.1
    fi
    # Note: previously, we had started XVFB directly here, as done here:
    # https://github.com/colmap/colmap/commit/606d3cd09931d78a3272f99b5e7a2cb6894e243e
    # Starting with Xenial, a new syntax in the .travis.yml file is used to replace
    # this, as described here:
    # https://docs.travis-ci.com/user/gui-and-headless-browsers/#using-services-xvfb

    # Finally, tell Qt to run offscreen.
    export QT_QPA_PLATFORM=offscreen
fi

# Insert the event type and python version, since we can be running multiple builds at the same time.
export SHOTGUN_TEST_ENTITY_SUFFIX="travis_${TRAVIS_EVENT_TYPE}_${TRAVIS_PYTHON_VERSION}_QT${QT_TEST_VER}"

# Specify a coverage file name that can be picked up by "coverage combine", i.e. a file named 
# .coverage.<something>
python -m coverage run --parallel-mode tests/run_tests.py

# Run these tests only if the integration tests environment variables are set.
if [ -z ${SHOTGUN_HOST+x} ]; then
    echo "Skipping integration tests, SHOTGUN_HOST is not set."
else
    # By forcing the temp dir, the integration test suite will not delete the destination
    # folder, as the variable is meant for debugging test output.
    # This is required or coverage combine will raise errors when merging
    # coverage files because some source files will have disappeared.
    SHOTGUN_TEST_TEMP=/var/tmp/coverage SHOTGUN_TEST_COVERAGE=1 python tests/integration_tests/run_integration_tests.py
fi

python -m coverage combine