"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------
"""

# thin proxy wrapper which finds the real tank and replaces itself with that

import os
import sys


# first look for our parent file
current_folder = os.path.abspath(os.path.dirname(__file__))
parent_file_name =  "core_%s.cfg" % sys.platform
parent_cfg_path = os.path.join(current_folder, "..", "..", parent_file_name)
parent_cfg_path = os.path.abspath(parent_cfg_path)

if not os.path.exists(parent_cfg_path):
    raise Exception("Sgtk: Cannot find referenced core configuration file '%s'!" % parent_cfg_path)

# now read our parent file
fh = open(parent_cfg_path, "rt")
try:
    parent_path = fh.readline()
finally:
    fh.close()

parent_python_path = os.path.join(parent_path, "install", "core", "python") 

if not os.path.exists(parent_python_path):
    raise Exception("Sgtk: Cannot find referenced core location '%s'" % parent_python_path)

# set up an env var to track the current pipeline configuration
# this is to help the tank core API figure out for example tank.tank_from_path()
# when using multiple work dev areas.
os.environ["TANK_CURRENT_PC"] = current_folder

# ok we got the parent location
# prepend this to the python path and reload the module
# this way we will load the 'real' tank! 
os.sys.path.insert(0, parent_python_path)
reload(sys.modules["tank"])

