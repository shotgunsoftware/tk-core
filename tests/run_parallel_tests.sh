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

find . -name "*.pyc" -delete

# We're not using our test runner defined in run_tests.py, but nose's, do define a bunch of environment
# variable that will help with the execution of the code.
# --processes=-1 processes means as many processes as there are core
# --process-timeouts=60 is set so that we don't have to worry about splitting complex TankTestBase derived
# classes into multiple classes or having to set _multiprocess_can_split_ to tell nose that each test
# inside the TankTestBase can be run in parallel. 60 seconds is double the amount of time it takes to run the
# tests, so it should be enough.
# -e run_integration_tests is to prevent nose to pick up that source file for testing.
PYTHONPATH=../python:python TK_TEST_FIXTURES=fixtures nosetests --processes=-1 --process-timeout=60 -e run_integration_tests $*