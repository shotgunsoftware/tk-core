#!/usr/bin/env bash
#
# Copyright (c) 2012 Shotgun Software, Inc
# ----------------------------------------------------

# this script is called by the main tank script
# the first parameter contains the path to the pipeline config root
# additional pameters are passed into the python script

core_install_root="$1/install/core"

# now add tank to the pythonpath
export PYTHONPATH="$core_install_root/python":${PYTHONPATH}

# now figure out which interpreter to use for Tank
# this is stored in a config file
curr_platform=`uname`
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

# get rid of the location param @ $1, no longer needed
shift

# execute the python script which does the actual work
exec $interpreter "$core_install_root/scripts/tank_cmd.py" $@
