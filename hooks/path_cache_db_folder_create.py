"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Hook to create the path cache sql lite db folder.

"""

from tank import Hook
import os

class PathCacheDbFolderCreate(Hook):

    def execute(self, db_path, **kwargs):
        """
        The default implementation creates the path cache db folder.
        """
        cache_folder = os.path.dirname(db_path)
        if not os.path.exists(cache_folder):
            old_umask = os.umask(0)
            try:
                os.mkdir(cache_folder, 0777)
            finally:
                os.umask(old_umask)
