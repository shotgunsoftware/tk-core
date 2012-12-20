"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Hook that gets executed every time an bundle has fully initialized.

"""

from tank import Hook
import os
 
class BundleInit(Hook):
    
    def execute(self, bundle, **kwargs):
        """
        Gets executed when the Tank bundle super class __init__
        is fully initialized.
        """
        pass