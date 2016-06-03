#!/bin/bash
# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

# First clean the repo
find . -name "*.pyc" -delete

# Define an output folder for files converted to be parsable with Python 3.
_PYTHON3_COMPATIBLE_CORE=/Users/jfboismenu/gitlocal/tk-core-3k

echo Tests will be run from "$_PYTHON3_COMPATIBLE_CORE"

# For smoothing differences between Python 2 and 3.
pip install six
# Our unittest 2 is broken under Python 3.
pip install unittest2
# Http2lib doesn't work in Python 3.
pip install httplib2

# links file to the destination folder.
python converter.py $_PYTHON3_COMPATIBLE_CORE unittest2 httplib2 /yaml/ .git
# import yaml from the python's site-packages
echo import yaml > ${_PYTHON3_COMPATIBLE_CORE}/python/tank_vendor/__init__.py
echo import httplib2 > ${_PYTHON3_COMPATIBLE_CORE}/python/tank_vendor/shotgun_api3/lib/__init__.py

if [ ! $? == 0 ] ; then
    exit
fi

pushd ${_PYTHON3_COMPATIBLE_CORE}/tests
PYTHONPATH=${_PYTHON3_COMPATIBLE_CORE}/python:$PYTHONPATH
python3  ./run_tests.py $*
popd > /dev/null
# Somehow the unit tests update this file???
git checkout fixtures
