"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Helper methods that extracts information about the current user.

"""

import os, sys

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

g_shotgun_user_cache = None

def get_shotgun_user(sg):
    """
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
    if g_shotgun_user_cache is None:        
        fields = ["id", "type", "email", "login", "name", "image"]
        local_login = get_login_name()
        g_shotgun_user_cache = sg.find_one("HumanUser", filters=[["login", "is", local_login]], fields=fields)
    
    return g_shotgun_user_cache
        
