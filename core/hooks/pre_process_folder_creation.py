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
        Executes before a process_filesystem_structure is run.

        * entity_type: the shotgun entity type for which the value is taken
        * entity_id: The entity id representing the data
        * preview: determines if the create or copy should be fulfilled
        * engine: an engine name for second pass

        """
        pass
