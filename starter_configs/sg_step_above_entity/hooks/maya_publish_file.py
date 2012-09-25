"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

I/O Hook which copies files on disk.

"""

import os
import shutil
from tank import Hook


class MayaPubPublishFile(Hook):
    
    def execute(self, source_path, target_path, **kwargs):
        shutil.copy(source_path, target_path) 
        # make it readonly
        os.chmod(target_path, 0444)
        
