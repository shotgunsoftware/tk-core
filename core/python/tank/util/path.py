"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Helper methods that extracts information about the current user.

"""

import os, sys

def append_path_to_env_var(env_var_name, path):
    """
    Appends the path to the given environment variable.
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
        paths.append(path)
    # and put it back
    os.environ[env_var_name] = env_var_sep.join(paths)
