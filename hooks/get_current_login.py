"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Hook that gets executed when the current user is being retrieved.

"""

from tank import Hook
import os, sys
 
class GetCurrentLogin(Hook):
    
    def execute(self, **kwargs):
        """
        Return the login name for the user currently logged in. This is typically used
        by tank to resolve against the 'login' field in the Shotgun users table in order
        to extract further metadata.
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
        