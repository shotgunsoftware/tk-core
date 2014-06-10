# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.


# thin proxy wrapper which finds the real tank and replaces itself with that

import os
import sys


# first look for our parent file
current_folder = os.path.abspath(os.path.dirname(__file__))
file_name_lookup = {"linux2": "core_Linux.cfg", "win32": "core_Windows.cfg", "darwin": "core_Darwin.cfg" }
parent_file_name =  file_name_lookup[sys.platform]
parent_cfg_path = os.path.join(current_folder, "..", "..", parent_file_name)
parent_cfg_path = os.path.abspath(parent_cfg_path)

if not os.path.exists(parent_cfg_path):
    raise Exception("Sgtk: Cannot find referenced core configuration file '%s'!" % parent_cfg_path)

# now read our parent file
fh = open(parent_cfg_path, "rt")
try:
    parent_path = fh.readline().strip()
    # expand any env vars that are used in the files. For example, you could have 
    # an env variable $STUDIO_TANK_PATH=/sgtk/software/shotgun/studio and your
    # and your parent file may just contain "$STUDIO_TANK_PATH" instead of an 
    # explicit path.
    parent_path = os.path.expandvars(parent_path)
finally:
    fh.close()

parent_python_path = os.path.join(parent_path, "install", "core", "python") 

if not os.path.exists(parent_python_path):
    raise Exception("Sgtk: Cannot find referenced core location '%s'" % parent_python_path)

# set up an env var to track the current pipeline configuration
# this is to help the tank core API figure out for example tank.tank_from_path()
# when using multiple work pipeline configurations for a single project

# make sure the TANK_CURRENT_PC points at the root of this pipeline configuration
pipeline_config = os.path.join(current_folder, "..", "..", "..", "..")
pipeline_config = os.path.abspath(pipeline_config)
os.environ["TANK_CURRENT_PC"] = pipeline_config

# ok we got the parent location
# prepend this to the python path and reload the module
# this way we will load the 'real' tank! 
os.sys.path.insert(0, parent_python_path)
reload(sys.modules["tank"])

