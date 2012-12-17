"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Hook that gets executed before a publish record is created in Shotgun.
This hook makes it possible to add custom fields to a publish before it gets created
aswell as modifying the content that is being pushed to shotgun.

"""

from tank import Hook
import os
 
class BeforeRegisterPublish(Hook):
    
    def execute(self, shotgun_data, context, **kwargs):
        """
        Gets executed just before a new publish entity is created in Shotgun.
        
        :param shotgun_data: All the data which will be passed to the shotgun create call
        :param context: The context of the publish
        
        :returns: return (potentially) modified data dictionary
        """
        
        # default implementation is just a pass-through.
        return shotgun_data