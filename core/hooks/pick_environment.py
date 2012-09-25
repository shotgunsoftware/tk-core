"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Hook which chooses an environment file to use based on the current context

"""

from tank import Hook



class PickEnvironment(Hook):

    def execute(self, context):
        # must have an entity
        if context.entity is None:
            return None
        
        if context.entity["type"] == "Shot":
            return "shot"
        elif context.entity["type"] == "Asset":
            return "asset"

        return None
