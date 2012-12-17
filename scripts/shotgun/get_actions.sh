#!/bin/bash -l
#
# Copyright (c) 2012 Shotgun Software, Inc
# ----------------------------------------------------

# called by the shotgun integration layer
# do not call by hand!

# note! We are using a login shell above so we have access to std env vars
# set in .bash_profile etc.

# note: $1 contains the project root, passed from shotgun

# now add tank to the pythonpath
studio_dir=$(dirname "$1")
tank_code_dir="$studio_dir/tank/install"
export PYTHONPATH="$tank_code_dir/core/python":${PYTHONPATH}

# now figure out which interpreter to use for Tank
# this is stored in a config file
curr_platform=`uname`
interpreter_config_file="$studio_dir/tank/config/core/interpreter_${curr_platform}.cfg"

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

# execute the python script which does the actual work
exec $interpreter "$tank_code_dir/core/scripts/shotgun/get_actions.py" $@
