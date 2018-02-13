# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Helper methods that do environment management
"""

import os, sys


def append_path_to_env_var(env_var_name, path, environ=None):
    """
    Append the path to the given environment variable.
    Creates the env var if it doesn't exist already.
    will concatenate paths using : on linux and ; on windows
    """
    
    return _add_path_to_env_var(env_var_name, path, prepend=False, environ)


def prepend_path_to_env_var(env_var_name, path, environ=None):
    """
    Prepend the path to the given environment variable.
    Creates the env var if it doesn't exist already.
    will concatenate paths using : on linux and ; on windows
    """
    
    return _add_path_to_env_var(env_var_name, path, prepend=True, environ)


def _add_path_to_env_var(env_var_name, path, prepend=False, environ=None):
    """
    Append or prepend the path to the given environment variable.
    Creates the env var if it doesn't exist already.
    will concatenate paths using : on linux and ; on windows
    """
    
    if environ is None:
        environ = os.environ
    
    if sys.platform == "win32":
        env_var_sep = ";"
    else:
        env_var_sep = ":"        
    
    paths = environ.get(env_var_name, "").split(env_var_sep)
    # clean up empty entries
    paths = [x for x in paths if x != ""]
    # Do not add path if it already exists in the list
    if path not in paths:
        if prepend:
            paths.insert(0, path)
        else:
            paths.append(path)
    # and put it back
    environ[env_var_name] = env_var_sep.join(paths)
    
    return environ
