"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

I/O Hook which creates folders on disk.

"""

from tank import Hook
import os

class PreProcessFolders(Hook):
    
    def execute(self, entity_type, entity_ids, preview, engine, **kwargs):
        """
        The default implementation creates folders recursively using open permissions.
        """
        pass
