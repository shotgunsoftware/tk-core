@echo off
rem 
rem Copyright (c) 2012 Shotgun Software, Inc
rem ----------------------------------------------------

rem CALLED BY SHOTGUN INTEGRATION LAYER
rem DO NOT CALL MANUALLY

rem note: the tank project root is contained in %1

rem add the tank core code location to the PYTHONPATH
set PYTHONPATH=%1\..\tank\install\core\python;%PYTHONPATH%

rem make sure interpreter cfg file exists
IF NOT EXIST %1\..\tank\config\core\interpreter_Windows.cfg GOTO NO_CONFIG

rem now figure out the location of the interpreter
set /p INTERPRETER= < %1\..\tank\config\core\interpreter_Windows.cfg

rem make sure interpreter exists
IF NOT EXIST %INTERPRETER% GOTO NO_INTERP

rem execute the python script which does the actual work.
%INTERPRETER% "%1\..\tank\install\core\scripts\shotgun\run_action.py" %*

rem pass along the return code
exit /b %ERRORLEVEL%

:NO_CONFIG
echo "Could not find interpreter configuration file!"
exit /b 1

:NO_INTERP
echo "Could not find interpreter %INTERPRETER% specified in configuration file!"
exit /b 1
