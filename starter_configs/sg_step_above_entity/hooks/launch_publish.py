"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Logic for launching an associated app

"""

from tank import Hook
import os

class LaunchAssociatedApp(Hook):
    def execute(self, context, path, **kwargs):
        engine = self.parent.engine
        status = False
        
        if path.endswith(".nk"):
            # nuke
            status = True
            engine.apps["tk-shotgun-launchnuke"].launch_from_path(path)
        elif path.endswith(".ma") or path.endswith(".mb"):
            # maya
            status = True
            engine.apps["tk-shotgun-launchmaya"].launch_from_path(path)
        elif path.endswith(".hip"):
            # houdini
            status = True
            engine.apps["tk-shotgun-launchhoudini"].launch_from_path(path)
                    
        return status
