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

./run_tests.sh shotgun_authentication_tests.test_connection && ./run_tests.sh util_tests.test_shotgun && ./run_tests.sh shotgun_authentication_tests.test_session_cache && ./run_tests.sh util_tests.test_login && ./run_tests.sh shotgun_authentication_tests.test_interactive_authentication --interactive 
