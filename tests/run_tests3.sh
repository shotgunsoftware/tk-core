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

./convert_py3k.sh $_PYTHON3_COMPATIBLE_CORE

if [ ! $? == 0 ] ; then
    exit
fi

pushd ${_PYTHON3_COMPATIBLE_CORE}/tests
PYTHONPATH=${_PYTHON3_COMPATIBLE_CORE}/python:$PYTHONPATH
python3  ./run_tests.py $*
popd > /dev/null
# Somehow the unit tests update this file???
git checkout fixtures
