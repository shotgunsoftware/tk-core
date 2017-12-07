# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Hook that gets executed every time an bundle has fully initialized.

"""

from tank import Hook
import os
 
class BundleInit(Hook):
    
    def execute(self, bundle, **kwargs):
        """
        Gets executed when the Toolkit bundle super class __init__
        is fully initialized.
        """
        pass