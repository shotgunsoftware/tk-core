#
# Copyright (c) 2012 Shotgun Software, Inc
# ----------------------------------------------------
#
"""
Before App Launch Hook

This hook is executed prior to application launch and is useful if you need
to set environment variables or run scripts as part of the app initialization.
"""

import os
from tank import Hook

class NukeBeforeAppLaunch(Hook):
    
    def execute(self, **kwargs):
        
        pass
        # accessing the current context (current shot, etc)
        # can be done via the parent object
        # my_app = self.parent.app
        # current_entity = my_app.context.entity
        
        # you can set environment variables like this:
        # os.environ["MY_SETTING"] = "foo bar"
        
        # if you are using a shared hook to cover multiple applications,
        # you can use the engine to figure out which application 
        # is currently being launched:
        # engine = self.parent.engine
        # if engine.name = "tk-maya":
        #     set maya specific stuff
        # elif engine.name = "tk-nuke":
        #     set nuke specific stuff
        
        