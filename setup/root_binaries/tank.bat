@echo off
rem 
rem Copyright (c) 2012 Shotgun Software, Inc
rem ----------------------------------------------------

rem -- get absolute location of this folder (note- always ends with a \)
set SELF_PATH=%~dp0

rem -- First of all, for performance, check if the command is shotgun_get_actions
IF "%1"=="shotgun_get_actions" GOTO CHECK_CACHE

rem -- set up an env var to track the current pipeline configuration
rem -- this is to help the tank core API figure out for example tank.tank_from_path()
rem -- when using multiple work dev areas.
rem -- since we are recursing upwards, only set it if it is not already set. 
rem -- we only set this when it is a pipeline location. Check this by looking for 
rem -- the templates file
set TEMPLATES_FILE=%SELF_PATH%config\core\templates.yml

rem -- if this var is not set AND the templates file exists, set the var.
IF "%TANK_CURRENT_PC%" == "" IF EXIST "%TEMPLATES_FILE%" set TANK_CURRENT_PC=%SELF_PATH% 

rem -- check if there is a local core
set LOCAL_SCRIPT=%SELF_PATH%install\core\scripts\tank_cmd.bat
IF NOT EXIST "%LOCAL_SCRIPT%" GOTO NO_LOCAL_INSTALL 

rem -- this is a local install! Run the wrapper script
call %LOCAL_SCRIPT% %SELF_PATH% %*

rem -- pass along the return code
exit /b %ERRORLEVEL%


rem --------------------------------------------------------------------------------------------
rem -- there is no local install
rem -- so try and get the parent and call its tank script
rem -- the parent location is stored in a config file
:NO_LOCAL_INSTALL

set PARENT_CONFIG_FILE=%SELF_PATH%install\core\core_Windows.cfg
IF NOT EXIST "%PARENT_CONFIG_FILE%" GOTO NO_PARENT_CONFIG

rem -- get contents of file
set /p PARENT_LOCATION= < "%PARENT_CONFIG_FILE%"
IF NOT EXIST "%PARENT_LOCATION%" GOTO NO_PARENT_LOCATION

rem -- all good, execute tank script in parent location
call %PARENT_LOCATION%\tank.bat %* --pc=%SELF_PATH%

rem -- pass along the return code
exit /b %ERRORLEVEL%


rem --------------------------------------------------------------------------------------------
rem -- check the shotgun actions cache
rem -- syntax ./tank shotgun_get_actions cache_file_name env_yml_file_name
rem -- returns 0 and outputs action cache contents to stdout on success
rem -- returns 1 if the cache file is older than the yml file.
rem -- returns 2 if the yml file does not exist
:CHECK_CACHE

set CACHE_FILE=%SELF_PATH%cache\%2
set ENV_FILE=%SELF_PATH%config\env\%3
set LOCAL_BASH=%SELF_PATH%install\core\setup\windows\bash.exe
set LOCAL_BASH_SCRIPT=%SELF_PATH%install\core\setup\windows\cache_check.sh

%LOCAL_BASH% %LOCAL_BASH_SCRIPT% %CACHE_FILE% %ENV_FILE%
echo Error level %ERRORLEVEL%
if "%ERRORLEVEL%" == "1" exit /b 1
if "%ERRORLEVEL%" == "2" exit /b 2 
rem -- cache is up to date - display it on screen
type "%CACHE_FILE%"
exit /b 0


rem --------------------------------------------------------------------------------------------
rem -- error traps

:NO_PARENT_CONFIG
echo Cannot find parent configuration file %PARENT_CONFIG_FILE%!
exit /b 1

:NO_PARENT_LOCATION
echo Cannot find parent location defined in file %PARENT_CONFIG_FILE%!
exit /b 1



