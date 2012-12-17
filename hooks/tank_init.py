"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Hook that gets executed every time a new tank instance is created.

"""

from tank import Hook
import os
 
class TankInit(Hook):
    
    def execute(self, **kwargs):
        """
        Gets executed when a new Tank instance is initialized.
        """
        pass