"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Hook for launching the app for a publish.

This hook typically looks at the extension of the input file
and based on this determine which launcher app to dispatch
the request to.

If no suitable launcher is found, return False, and the app
will launch the file in default viewer. 
"""

from tank import Hook
import os

class LaunchAssociatedApp(Hook):
    def execute(self, path, context, **kwargs):
        
        engine = self.parent.engine
        status = False
        
        ########################################################################
        # Example implementation below:
        
        if path.endswith(".nk"):
            # nuke
            if "tk-shotgun-launchnuke" in engine.apps:
                # looks like there is a nuke launcher installed in this system!
                status = True
                engine.apps["tk-shotgun-launchnuke"].launch_from_path(path)

        elif path.endswith(".ma") or path.endswith(".mb"):
            # maya
            if "tk-shotgun-launchmaya" in engine.apps:
                # looks like there is a maya launcher installed in this system!
                status = True
                engine.apps["tk-shotgun-launchmaya"].launch_from_path(path)
                    
        return status
