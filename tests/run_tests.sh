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

#
# Allows to run the unit tests against the python executable. The actual version is determined
# by the user's environment.
#

find . -name "*.pyc" -delete
python `dirname $0`/run_tests.py $*
