@echo off
rem Copyright (c) 2011 Shotgun Software, Inc


IF "%1"=="" GOTO NO_ROOT

rem add the tank core code location to the PYTHONPATH
set PYTHONPATH=%1\tank\install\core\python;%PYTHONPATH%

rem make sure interpreter cfg file exists
IF NOT EXIST %1\tank\config\core\interpreter_Windows.cfg GOTO NO_CONFIG

rem now figure out the location of the interpreter
set /p INTERPRETER= < %1\tank\config\core\interpreter_Windows.cfg

rem make sure interpreter exists
IF NOT EXIST %INTERPRETER% GOTO NO_INTERP

rem save the current path
set CUR_DIR=%~dp0

rem throw the first parameter away
shift
set PARAMS=%1
:loop
    shift
    if [%1]==[] goto afterloop
    set PARAMS=%PARAMS% %1
goto loop

:afterloop
rem execute the python script which does the actual work.
%INTERPRETER% "%CUR_DIR%\run_shell.py"  %PARAMS%

rem pass along the return code
exit /b %ERRORLEVEL%

:NO_CONFIG
echo "Could not find interpreter configuration file: %1\tank\config\core\interpreter_Windows.cfg"
exit /b 1

:NO_INTERP
echo "Could not find interpreter %INTERPRETER% specified in configuration file!"
exit /b 1


:NO_ROOT
echo "Please supply Tank root path"
exit /b 1


