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
_PYTHON3_COMPATIBLE_CORE=${TMPDIR}tk-core

echo $_PYTHON3_COMPATIBLE_CORE

# Create that output folder
rm -rf $_PYTHON3_COMPATIBLE_CORE
mkdir -p $_PYTHON3_COMPATIBLE_CORE/hooks
mkdir -p $_PYTHON3_COMPATIBLE_CORE/python
mkdir -p $_PYTHON3_COMPATIBLE_CORE/tests

# Copy all sources to that folder
cp -R ../hooks/ ${_PYTHON3_COMPATIBLE_CORE}/hooks
cp -R ../python/ ${_PYTHON3_COMPATIBLE_CORE}/python

# Unit tests fixtures are huuuuuuge, so hardlink everything instead.
# Thanks stackexchange: http://unix.stackexchange.com/a/202435
dst=${_PYTHON3_COMPATIBLE_CORE}/tests
src=.
absolute_dst=$(umask 077 && mkdir -p -- "$dst" && cd -P -- "$dst" && pwd -P) && (cd -P -- "$src" && pax -rwlpe . "$absolute_dst")

# For erasing differences between Python 2 and 3.
pip install six

# Our unittest 2 is broken under Python 3.
pip install unittest2
rm -rf ${_PYTHON3_COMPATIBLE_CORE}/tests/python/unittest2

# Http2lib doesn't work in Python 3.
pip install httplib2
rm -rf ${_PYTHON3_COMPATIBLE_CORE}/python/tank_vendor/shotgun_api3/lib/httplib2

# 2to3 chokes on the yaml library, so replace it with the official python 3 one.
rm -rf ${_PYTHON3_COMPATIBLE_CORE}/python/tank_vendor/yaml
echo import yaml > ${_PYTHON3_COMPATIBLE_CORE}/python/tank_vendor/__init__.py

# Convert the sources to be parsable in Python 3.
# We'll only convert except and print statements. Print statements could actually be done
# in code with __future__ but it's going to cost us time converting these and we're short on
# time for this hackathon.
2to3 -w -f except -f print -f numliterals -f raise $_PYTHON3_COMPATIBLE_CORE
if [ ! $? == 0 ] ; then
    exit
fi

2to3 -w -f import $_PYTHON3_COMPATIBLE_CORE/python/tank_vendor/yaml

PYTHONPATH=${_PYTHON3_COMPATIBLE_CORE}/python:$PYTHONPATH
cd ${_PYTHON3_COMPATIBLE_CORE}/tests
python3  ./run_tests.py $*

