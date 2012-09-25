"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Hook to setup the HOUDINI_PATH environment variable.

"""

import os
import shutil
import platform

import tank
from tank import Hook

class SetHoudiniPath(Hook):
    
    def execute(self, prepend_paths=None, **kwargs):
        """
        Sets the HOUDINI_PATH environment variable.

        This file should include any site specific path for the houdini path.

        :param list prepend_paths: list of paths that should be places at the front of the HOUDINI_PATH

        """
        if prepend_paths:
            for path in prepend_paths:
                tank.util.append_path_to_env_var("HOUDINI_PATH", path)

        system = platform.system()
        if system == "Windows":
            pass
        elif system == "Darwin":
            tank.util.append_path_to_env_var(
                "HOUDINI_PATH", os.path.expanduser("~/Library/Preferences/houdini/12.0/")
            )
            tank.util.append_path_to_env_var(
                "HOUDINI_PATH", 
                "/Library/Frameworks/Houdini.framework/Versions/12.0.543.9/Resources/houdini"
            )

        elif system == "Linux":
            pass
        else:
            raise Exception("Platform '%s' is not supported." % system)