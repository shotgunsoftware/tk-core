"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------
"""

from tank import Hook

class TestHook(Hook):
    
    def execute(self, dummy_param):
        return True
        
