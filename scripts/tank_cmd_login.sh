#!/bin/bash --login
# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

# note! this is a clone of the tank_cmd.sh script
# with the only difference that it uses a login shell
# e.g. bash started with the --login parameter.
# this is useful if you are starting from a blank environment,
# for example the java applet. Make sure to keep the two scripts in sync.
#
# note 2: because we need to pass an arg to bash, we cannot use env
#         for the shebang.

# this script is called by the main tank script
# the first parameter contains the path to the pipeline config root
# additional parameters are passed into the python script

# first set the pythonpath and get a path to the install root

uname_os_str=`uname`

if [[ "$uname_os_str" == MINGW64_NT* ]] || [[ "$uname_os_str" == MINGW32_NT* ]];
then
	curr_platform="Windows"
	# see http://stackoverflow.com/questions/12015348/msys-path-conversion-or-cygpath-for-msys/12063651#12063651
	core_install_root=`sh -c "(cd $1 2</dev/null && pwd -W) || echo $1 | sed 's/\\//\\\\/g;s/^\\\\\([a-z]\)\\\\/\\1:\\\\/'"`
	core_install_root="${core_install_root}/install/core"
	export PYTHONPATH="$core_install_root/python;"${PYTHONPATH}
elif [[ "$uname_os_str" ==  CYGWIN_NT* ]];
then
	curr_platform="Windows"
	core_install_root="$( cygpath -lw $1 )/install/core"
	export PYTHONPATH="$core_install_root/python;"${PYTHONPATH}
else
    curr_platform=`uname`
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

# Convert windows interpreter paths to forward-slash
if [[ "$uname_os_str" == CYGWIN_NT* ]];
then
    interpreter=$( cygpath -u $interpreter )
fi

# Expand environment variables
interpreter=`eval echo $interpreter`

# and check that it exists...
if [ ! -f "$interpreter" ];
then
    echo "Cannot find interpreter $interpreter defined in config file $interpreter_config_file!"
    exit 1
fi

# execute the python script which does the actual work
exec $interpreter "$core_install_root/scripts/tank_cmd.py" "$@"
