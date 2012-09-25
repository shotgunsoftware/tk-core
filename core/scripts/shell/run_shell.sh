#!/bin/bash
# Copyright (c) 2011 Shotgun Software, Inc


# the first argument is the tank studio root
studio_dir=$1

# now figure out which interpreter to use 
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
exec $interpreter `dirname $0`/run_shell.py ${@:2}
