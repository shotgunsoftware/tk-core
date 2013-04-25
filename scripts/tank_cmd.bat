@echo off
rem 
rem Copyright (c) 2012 Shotgun Software, Inc
rem ----------------------------------------------------

rem -- this script is called by the main tank script
rem -- the first parameter contains the path to the pipeline config root
rem -- additional pameters are passed into the python script

rem -- now add tank to the pythonpath
set PYTHONPATH=%1install\core\python;%PYTHONPATH%

rem -- now figure out which interpreter to use for Tank
rem -- this is stored in a config file
set INTERPRETER_CONFIG_FILE=%1config\core\interpreter_Windows.cfg
IF NOT EXIST "%INTERPRETER_CONFIG_FILE%" GOTO NO_INTERPRETER_CONFIG

rem -- now get path to python interpreter by reading config file
set /p INTERPRETER= < "%INTERPRETER_CONFIG_FILE%"
IF NOT EXIST "%INTERPRETER%" GOTO NO_INTERPRETER

rem -- execute the python script which does the actual work.
%INTERPRETER% "%1install\core\scripts\tank_cmd.py" %*

rem -- pass along the return code
exit /b %ERRORLEVEL%

:NO_INTERPRETER_CONFIG
echo "Cannot find interpreter configuration file %INTERPRETER_CONFIG_FILE%!"
exit /b 1

:NO_INTERPRETER
echo "Could not find interpreter %INTERPRETER% specified in configuration file!"
exit /b 1