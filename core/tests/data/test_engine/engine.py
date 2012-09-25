"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

A simple engine to support unit tests.
"""

from tank.platform import Engine
import tank
import sys


class TestEngine(Engine):
    
    def init_engine(self):
        pass
                
    ##########################################################################################
    # logging interfaces

    def log_debug(self, msg):
        if self.get_setting("debug_logging", False):
            sys.stdout.write("DEBUG: %s\n" % msg)
    
    def log_info(self, msg):
        sys.stdout.write("%s\n" % msg)
        
    def log_warning(self, msg):
        sys.stdout.write("WARNING: %s\n" % msg)
    
    def log_error(self, msg):
        sys.stdout.write("ERROR: %s\n" % msg)
