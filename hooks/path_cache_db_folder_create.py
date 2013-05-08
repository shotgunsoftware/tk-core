"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Hook to create the path cache sql lite db folder.

"""

from tank import Hook
import os

class PathCacheDbFolderCreate(Hook):

    def execute(self, cache_folder, **kwargs):
        """
        The default implementation creates the path cache db folder.
        """
        old_umask = os.umask(0)
        try:
            os.mkdir(cache_folder, 0777)
        finally:
            os.umask(old_umask)
