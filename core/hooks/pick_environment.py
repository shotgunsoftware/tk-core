"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Hook which chooses an environment file to use based on the current context.
This file is almost always overridden by a standard config.

"""

from tank import Hook

class PickEnvironment(Hook):

    def execute(self, context, **kwargs):
        """
        The default implementation assumes there are two environments, called shot 
        and asset, and switches to these based on entity type.
        """
        
        # must have an entity
        if context.entity is None:
            return None
        
        if context.entity["type"] == "Shot":
            return "shot"
        elif context.entity["type"] == "Asset":
            return "asset"

        return None
