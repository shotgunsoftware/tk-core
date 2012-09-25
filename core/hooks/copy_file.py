"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

I/O Hook which copies a file from one location to another.

"""

from tank import Hook
import shutil
import os

class CopyFile(Hook):    
    def execute(self, source_path, target_path):
        if not os.path.exists(target_path):
            shutil.copy(source_path, target_path)
