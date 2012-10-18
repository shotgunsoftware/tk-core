"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

I/O Hook which copies files on disk.

"""

from tank import Hook
import shutil
import os

class NukePubPublishFile(Hook):
    
    def execute(self, source_path, target_path, **kwargs):
        
        # create the publish folder if it doesn't exist
        dirname = os.path.dirname(target_path)
        if not os.path.isdir(dirname):            
            old_umask = os.umask(0)
            os.makedirs(dirname, 0777)
            os.umask(old_umask)            
        
        shutil.copy(source_path, target_path) 
        # make it readonly
        os.chmod(target_path, 0444)
        
