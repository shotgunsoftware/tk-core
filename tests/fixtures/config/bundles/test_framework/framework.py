# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import sgtk

class TestFramework(sgtk.platform.Framework):
    
    ##########################################################################################
    # init and destroy
            
    def init_framework(self):
        self.log_debug("%s: Initializing..." % self)
    
    def destroy_framework(self):
        self.log_debug("%s: Destroying..." % self)
    
    
