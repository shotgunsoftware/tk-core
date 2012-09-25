"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------
"""
from tank import Hook

class PickEnvironment(Hook):

    def execute(self, context):
        return "test"

