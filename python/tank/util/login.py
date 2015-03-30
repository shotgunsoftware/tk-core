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
Helper methods that extracts information about the current user.

"""

import os
import sys

from ..platform import constants
from tank_vendor import shotgun_authentication as sg_auth


def get_login_name():
    """
    Retrieves the login name of the current user.
    Returns None if no login name was found
    """
    if sys.platform == "win32": 
        # http://stackoverflow.com/questions/117014/how-to-retrieve-name-of-current-windows-user-ad-or-local-using-python
        return os.environ.get("USERNAME", None)
    else:
        try:
            import pwd
            pwd_entry = pwd.getpwuid(os.geteuid())
            return pwd_entry[0]
        except:
            return None

# note! Because the shotgun caching method can return None, to indicate that no
# user was found, we cannot use a None value to indicate that the cache has not been
# populated. 
g_shotgun_user_cache = "unknown"
g_shotgun_current_user_cache = "unknown"

def get_shotgun_user(sg):
    """
    
    ---- DEPRECATED ---- user get_current_user(tk) instead
    
    Retrieves a shotgun user dict
    for the current user. Returns None if the user is not found in shotgun.
    
    Returns the following fields:
    
    * id
    * type
    * email
    * login
    * name
    * image (thumbnail)
    
    This method connects to shotgun.
    """    
    global g_shotgun_user_cache    
    if g_shotgun_user_cache == "unknown":        
        fields = ["id", "type", "email", "login", "name", "image"]
        local_login = get_login_name()
        g_shotgun_user_cache = sg.find_one("HumanUser", filters=[["login", "is", local_login]], fields=fields)
    
    return g_shotgun_user_cache

def get_current_user(tk):
    """
    Retrieves the current user as a dictionary of metadata values. Note: This method connects to
    shotgun the first time around. The result is then cached to reduce latency.
    :returns: None if the user is not found in shotgun. Otherwise, it returns a dictionary
              with the following fields:
                 * id
                 * type
                 * email
                 * login
                 * name
                 * image url (thumbnail)
    """
    global g_shotgun_current_user_cache
    if g_shotgun_current_user_cache != "unknown":
        return g_shotgun_current_user_cache

    from .. import api

    user = api.get_current_user()

    if sg_auth.is_script_user(user):
        # If we have a script user, try to find a matching user using the os user name.
        # call hook to get current login
        current_login = tk.execute_core_hook(constants.CURRENT_LOGIN_HOOK_NAME)
    elif sg_auth.is_session_user(user):
        # If we have a human user, simply use the login value.
        current_login = user.get_login()
    else:
        # Something is wrong, no current login available.
        current_login = None

    if current_login is None:
        g_shotgun_current_user_cache = None
    else:
        fields = ["id", "type", "email", "login", "name", "image"]
        g_shotgun_current_user_cache = tk.shotgun.find_one(
            "HumanUser",
            filters=[["login", "is", current_login]],
            fields=fields
        )

    return g_shotgun_current_user_cache
