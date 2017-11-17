:: Copyright (c) 2017 Shotgun Software Inc.
::
:: CONFIDENTIAL AND PROPRIETARY
::
:: This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
:: Source Code License included in this distribution package. See LICENSE.
:: By accessing, using, copying or modifying this work you indicate your
:: agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
:: not expressly granted therein are reserved by Shotgun Software Inc.

::
:: Allows to run the unit tests against the python executable. The actual version is determined
:: by the user's environment.
::

@echo off

python -c "from __future__ import print_function; import sys; print('.'.join(str(token) for token in sys.version_info[:3]))" > version_str.txt
for /f "usebackq tokens=*" %%G in (version_str.txt) do (CALL SET VERSION_STR=%%G)
del version_str.txt
CALL SET VENV_FOLDER=..\venvs\windows\venv_%VERSION_STR%
%VENV_FOLDER%/Scripts/activate.bat

python %~dp0\run_tests.py %*
