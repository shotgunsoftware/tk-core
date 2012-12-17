"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

I/O Hook which creates folders on disk.

"""

from tank import Hook
import os

class CreateFolders(Hook):
    
    def execute(self, path, sg_entity=None, **kwargs):
        """
        The default implementation creates folders recursively using open permissions.
        """
        if not os.path.exists(path):
            old_umask = os.umask(0)
            os.makedirs(path, 0777)
            os.umask(old_umask)