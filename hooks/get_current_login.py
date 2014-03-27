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
Hook that gets executed when the current user is being retrieved.

"""

from tank import Hook
import os, sys
 
class GetCurrentLogin(Hook):
    
    def execute(self, **kwargs):
        """
        Return the login name for the user currently logged in. This is typically used
        by Toolkit to resolve against the 'login' field in the Shotgun users table in order
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
        