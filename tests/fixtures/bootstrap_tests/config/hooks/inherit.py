# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.


import sgtk

HookBaseClass = sgtk.get_hook_baseclass()


class TestHook(HookBaseClass):
    
    def foo2(self, bar):
        
        val = HookBaseClass.foo2(self, bar)
        
        return "custom class %s" % val
        
