"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

I/O Hook which creates folders on disk.

"""

from tank import Hook
import os

class PostProcessFolders(Hook):
    
    def execute(self, num_entities_processed, processed_items, preview, **kwargs):
        """
        The default implementation creates folders recursively using open permissions.
        """
        pass
