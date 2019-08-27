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

set PYTHONPATH=tests/python/third_party;tests/python;python
%PYTHON%\python tests/run_tests.py

:: FIXME: This approach does not scale...
if not %ERRORLEVEL% == 0 exit /b %ERRORLEVEL%

:: This suffix for appveyor is sufficient, since we never run more than one build at a time.
set SHOTGUN_TEST_ENTITY_SUFFIX=app_veyor

:: Run these tests only if the integration tests environment variables are set.
IF DEFINED SHOTGUN_HOST (
    %PYTHON%\python tests\integration_tests\offline_workflow.py
    :: FIXME: This approach does not scale...
    if not %ERRORLEVEL% == 0 exit /b %ERRORLEVEL%

    %PYTHON%\python tests\integration_tests\tank_commands.py
    if not %ERRORLEVEL% == 0 exit /b %ERRORLEVEL%

    %PYTHON%\python tests\integration_tests\multi_bootstrap.py
    if not %ERRORLEVEL% == 0 exit /b %ERRORLEVEL%

) ELSE (
    ECHO "Skipping integration tests, SHOTGUN_HOST is not set."
)
