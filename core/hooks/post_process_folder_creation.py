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
        Gets called after a process_filesystem_structure request.  
        * num_entities_processed: the number of entities folders will be created for.
        * processed_items: list of dicts in the form of:
                                {
                                 'path': <Path to Create>,
                                 'entity': <Entity if folder has one>,
                                 'metadata': <A dict of folder metadata if defined>,
                                 'action': <A string describing the action (create_folder, copy_file)>
                                }

        * preview: determines if the file system operations should be fulfilled.
        """
        pass
