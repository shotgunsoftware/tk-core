#!/usr/bin/env bash
#
# Copyright (c) 2012 Shotgun Software, Inc
# ----------------------------------------------------

# note! any changes made here need to be reflected in
# the tank_cmd_login.sh script

# this script is called by the main tank script
# the first parameter contains the path to the pipeline config root
# additional pameters are passed into the python script


curr_platform=`uname`

# Pretty sloppy but takes care of allowing the tank.sh script to run via
# git-bash as well as cygwin.
# now add tank to the pythonpath
if [[ "$curr_platform" == MINGW32_NT* ]];
then
	curr_platform="Windows"
	core_install_root="$( pwd -W )/install/core"
	export PYTHONPATH="$core_install_root/python;"${PYTHONPATH}
elif [[ "$curr_platform" ==  CYGWIN_NT* ]];
then
	curr_platform="Windows"
	core_install_root="$( cygpath -lw $1 )/install/core"
	export PYTHONPATH="$core_install_root/python;"${PYTHONPATH}
else
	core_install_root="$1/install/core"
	export PYTHONPATH="$core_install_root/python":${PYTHONPATH}
fi

# now figure out which interpreter to use for Tank
# this is stored in a config file
interpreter_config_file="$1/config/core/interpreter_${curr_platform}.cfg"

if [ ! -f "$interpreter_config_file" ];
then
    echo "Cannot find interpreter configuration file $interpreter_config_file!"
    exit 1
fi

# now get path to python interpreter by reading config file
interpreter=`cat "$interpreter_config_file"`

# and check that it exists...
if [ ! -f "$interpreter" ];
then
    echo "Cannot find interpreter $interpreter defined in config file $interpreter_config_file!"
    exit 1
fi

# Cygwin wants the python path back in it's unix style :(.
if [[ `uname` == CYGWIN_NT* ]];
then
	interpreter=$( cygpath -u $interpreter )
fi

# execute the python script which does the actual work
exec $interpreter "$core_install_root/scripts/tank_cmd.py" "$@"
