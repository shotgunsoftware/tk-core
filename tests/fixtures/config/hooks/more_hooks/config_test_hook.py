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
import sgtk

HookBaseClass = sgtk.get_hook_baseclass()


class AnotherTestHook(HookBaseClass):
    
    def test_inheritance_disk_location(self):

        # get test data from base class using disk_location
        disk_location_base = super(AnotherTestHook, self).test_disk_location()
        # test our disk_location
        our_disk_location = os.path.join(self.disk_location, "toolkitty.png")

        return disk_location_base, our_disk_location
