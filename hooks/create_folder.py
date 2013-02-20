"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

DEPRECATED!! This hook is not used by the Tank Core Platform
and is just bundled for backwards compatibility. (20 Feb 2013)

It will be removed at some stage - do not use it.

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