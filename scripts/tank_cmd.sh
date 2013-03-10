#!/usr/bin/env bash
#
# Copyright (c) 2012 Shotgun Software, Inc
# ----------------------------------------------------


# get absolute location of this script
SELF_PATH=$(cd -P -- "$(dirname -- "$0")" && pwd -P) && SELF_PATH=$SELF_PATH/$(basename -- "$0")
 
# resolve symlinks
while [ -h $SELF_PATH ]; do
    # 1) cd to directory of the symlink
    # 2) cd to the directory of where the symlink points
    # 3) get the pwd
    # 4) append the basename
    DIR=$(dirname -- "$SELF_PATH")
    SYM=$(readlink $SELF_PATH)
    SELF_PATH=$(cd $DIR && cd $(dirname -- "$SYM") && pwd)/$(basename -- "$SYM")
done

# chop off the file name
SELF_PATH=$(dirname $SELF_PATH)



# now add tank to the pythonpath
export PYTHONPATH="$SELF_PATH/../python":${PYTHONPATH}

# now figure out which interpreter to use for Tank
# this is stored in a config file
curr_platform=`uname`
interpreter_config_file="$SELF_PATH/../../../config/core/interpreter_${curr_platform}.cfg"

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
exec $interpreter "$SELF_PATH/tank_cmd.py" $@
