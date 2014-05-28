@echo off

rem  Copyright (c) 2013 Shotgun Software Inc.
rem  
rem  CONFIDENTIAL AND PROPRIETARY
rem  
rem  This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
rem  Source Code License included in this distribution package. See LICENSE.
rem  By accessing, using, copying or modifying this work you indicate your 
rem  agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
rem  not expressly granted therein are reserved by Shotgun Software Inc.

setlocal EnableExtensions

rem -- track when this file is launched:
echo DEBUG [%TIME%]: Starting tank_cmd.bat

rem -- this script is called by the main tank script
rem -- the first parameter contains the path to the pipeline config root
rem -- additional pameters are passed into the python script
rem -- now add tank to the pythonpath
set PYTHONPATH=%1install\core\python\tank.zip;%1install\core\python;%PYTHONPATH%

rem -- now figure out which interpreter to use for Tank
rem -- this is stored in a config file
set INTERPRETER_CONFIG_FILE=%1config\core\interpreter_Windows.cfg
IF NOT EXIST "%INTERPRETER_CONFIG_FILE%" GOTO NO_INTERPRETER_CONFIG

rem -- now get path to python interpreter by reading config file
for /f "tokens=*" %%G in (%INTERPRETER_CONFIG_FILE%) do (SET PYTHON_INTERPRETER=%%G)
IF NOT EXIST %PYTHON_INTERPRETER% GOTO NO_INTERPRETER

rem -- execute the python script which does the actual work.
echo DEBUG [%TIME%]: Starting Python interpreter '%PYTHON_INTERPRETER%'
%PYTHON_INTERPRETER% "%1install\core\scripts\tank_cmd.py" %*
echo DEBUG [%TIME%]: Python has exited!

rem -- pass along the return code
exit /b %ERRORLEVEL%

:NO_INTERPRETER_CONFIG
echo "Cannot find interpreter configuration file %INTERPRETER_CONFIG_FILE%!"
exit /b 1

:NO_INTERPRETER
echo "Could not find interpreter %PYTHON_INTERPRETER% specified in configuration file!"
exit /b 1
