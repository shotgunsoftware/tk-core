"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Hook that gets executed every time an engine has fully initialized.

"""

from tank import Hook
import os
 
class EngineInit(Hook):
    
    def execute(self, engine, **kwargs):
        """
        Gets executed when a Tank engine has fully initialized.
        At this point, all applications and frameworks have been loaded,
        and the engine is fully operational.
        """
        pass