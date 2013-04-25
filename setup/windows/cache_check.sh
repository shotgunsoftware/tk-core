#
# Copyright (c) 2012 Shotgun Software, Inc
# ----------------------------------------------------

# very minor bash script used to compare the modification 
# time stamps between two files - this turns out to be 
# extremely difficult using normal bat files.
#
# this mimics the behaviour in the main bash tank executable
#
# inputs:
# $1 - full path to a cache file
# $2 - full path to a yml file
#
# returns:
# exit code 2 - yml file could not be found
# exit code 1 - cache file is older than yml file
# exit code 0 - cache file is up to date

# return 2 if the yml file does not exist
if [ ! -f "$2" ];
then
    exit 2
fi    
    
# return cache contents if cache is up to date
if [ "$1" -nt "$2" ]; then
    exit 0
else
    exit 1
fi
