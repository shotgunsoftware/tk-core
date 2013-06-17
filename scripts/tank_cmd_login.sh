#!/bin/bash --login
#
# Copyright (c) 2012 Shotgun Software, Inc
# ----------------------------------------------------

# note! this is a clone of the tank_cmd.sh script
# with the only difference that it uses a login shell
# e.g. bash started with the --login parameter.
# this is useful if you are starting from a blank environment,
# for example the java applet. Make sure to keep the two scripts in sync.
#
# note 2: because we need to pass an arg to bash, we cannot use env.

# this script is called by the main tank script
# the first parameter contains the path to the pipeline config root
# additional pameters are passed into the python script

core_install_root="$1/install/core"

# now add tank to the pythonpath
export PYTHONPATH="$core_install_root/python":${PYTHONPATH}

# now figure out which interpreter to use for Tank
# this is stored in a config file
curr_platform=`uname`
if [[ "${curr_platform}" == MINGW32_NT* ]] || [[ "${curr_platform}" ==  CYGWIN_NT* ]];
then
    curr_platform="Windows"
fi
interpreter_config_file="$1/config/core/interpreter_${curr_platform}.cfg"

if [ ! -f "$interpreter_config_file" ];
then
    echo "Cannot find interpreter configuration file $interpreter_config_file!"
    exit 1
fi

# now get path to python interpreter by reading config file
interpreter=`cat "$interpreter_config_file"`

if [[ `uname` == CYGWIN_NT* ]];
then
    interpreter=$( cygpath -u $interpreter )
fi

# and check that it exists...
if [ ! -f "$interpreter" ];
then
    echo "Cannot find interpreter $interpreter defined in config file $interpreter_config_file!"
    exit 1
fi

# execute the python script which does the actual work
exec $interpreter "$core_install_root/scripts/tank_cmd.py" "$@"
