:: Copyright (c) 2018 Shotgun Software Inc.
::
:: CONFIDENTIAL AND PROPRIETARY
::
:: This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
:: Source Code License included in this distribution package. See LICENSE.
:: By accessing, using, copying or modifying this work you indicate your
:: agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
:: not expressly granted therein are reserved by Shotgun Software Inc.

::
:: This file is run by the appveyor builds.
::

set PYTHONPATH=tests/python/third_party
%PYTHON%\python tests/run_tests.py

:: Run these tests only if the integration tests environment variables are set.
IF DEFINED SHOTGUN_HOST (%PYTHON%\python tests/integration_tests/offline_workflow.py) ELSE (ECHO "Skipping integration tests, SHOTGUN_HOST is not set.")
