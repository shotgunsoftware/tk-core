# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
from tank import Hook


class TestHook(Hook):
    
    def execute(self, dummy_param):
        return True
        
    def second_method(self, another_dummy_param):
        return True

    def logging_method(self):
        self.logger.info("hello toolkitty")

    def test_disk_location(self):
        return os.path.join(self.disk_location, "toolkitty.png")
