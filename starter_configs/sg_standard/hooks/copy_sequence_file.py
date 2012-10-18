"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

I/O Hook which copies files on disk.

"""

from tank import Hook
import shutil
import os

class NukeCopySequenceFile(Hook):
    
    def execute(self, source_path, target_path, **kwargs):
        shutil.copy(source_path, target_path) 
        # make it readonly
        os.chmod(target_path, 0444)
        
