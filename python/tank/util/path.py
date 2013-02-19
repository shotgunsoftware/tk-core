"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Helper methods that do path management.

"""

import os, sys


def append_path_to_env_var(env_var_name, path):
    """
    Append the path to the given environment variable.
    Creates the env var if it doesn't exist already.
    will concatenate paths using : on linux and ; on windows
    """
    
    return add_path_to_env_var(env_var_name, path, prepend=False)


def prepend_path_to_env_var(env_var_name, path):
    """
    Prepend the path to the given environment variable.
    Creates the env var if it doesn't exist already.
    will concatenate paths using : on linux and ; on windows
    """
    
    return add_path_to_env_var(env_var_name, path, prepend=True)


def add_path_to_env_var(env_var_name, path, prepend=False):
    """
    Append or prepend the path to the given environment variable.
    Creates the env var if it doesn't exist already.
    will concatenate paths using : on linux and ; on windows
    """
    
    if sys.platform == "win32":
        env_var_sep = ";"
    else:
        env_var_sep = ":"        
    
    paths = os.environ.get(env_var_name, "").split(env_var_sep)
    # clean up empty entries
    paths = [x for x in paths if x != ""]
    # Do not add path if it already exists in the list
    if path not in paths:
        if prepend:
            paths.insert(0, path)
        else:
            paths.append(path)
    # and put it back
    os.environ[env_var_name] = env_var_sep.join(paths)
