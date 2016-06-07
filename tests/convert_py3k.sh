#!/bin/bash
# For smoothing differences between Python 2 and 3.
pip install six
# Our unittest 2 is broken under Python 3.
pip install unittest2
# Http2lib doesn't work in Python 3.
pip install httplib2

# links file to the destination folder.
python converter.py ~/gitlocal/tk-core $1 unittest2 httplib2 /yaml/ .git mock.py
# import yaml from the python's site-packages
echo import yaml > $1/python/tank_vendor/__init__.py
echo import httplib2 > $1/python/tank_vendor/shotgun_api3/lib/__init__.py

if [ ! $? == 0 ] ; then
    exit
fi