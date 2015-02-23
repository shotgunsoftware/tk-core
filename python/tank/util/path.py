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
Helper methods that do path management.

"""

import os
import sys
import errno
import urlparse
from tank.errors import TankError


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


def get_local_site_cache_location(base_url):
    """
    Returns the location of the site cache root based on a site.
    :param base_url: Site we need to compute the root path for.
    :returns: An absolute path to the site cache root.
    """
    if sys.platform == "darwin":
        root = os.path.expanduser("~/Library/Caches/Shotgun")
    elif sys.platform == "win32":
        root = os.path.join(os.environ["APPDATA"], "Shotgun")
    elif sys.platform.startswith("linux"):
        root = os.path.expanduser("~/.shotgun")

    # get site only; https://www.foo.com:8080 -> www.foo.com
    base_url = urlparse.urlparse(base_url)[1].split(":")[0]

    return os.path.join(root, base_url)
