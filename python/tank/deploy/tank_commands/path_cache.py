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
Methods for handling of the tank command

"""

from ... import pipelineconfig


from ...util import shotgun
from ...platform import constants
from ...errors import TankError

from .action_base import Action

import sys
import os


class PathCacheInfoAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "folder_info", 
                        Action.GLOBAL, 
                        "Shows a breakdown of all the folders created for a particular entity.", 
                        "Admin")
    
    def run(self, log, args):
        
        log.info("Placeholder contents")

class DeleteFolderAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "delete_folder", 
                        Action.GLOBAL, 
                        ("Controls deletion of folders that represent Shotgun entities "
                         "such as Shots and Assets."), 
                        "Admin")
    
    def run(self, log, args):
        
        log.info("Placeholder contents")


class RenameFolderAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "rename_folder", 
                        Action.GLOBAL, 
                        ("Controls renaming of folders that represent Shotgun entities "
                         "such as Shots and Assets."), 
                        "Admin")
    
    def run(self, log, args):
        
        log.info("Placeholder contents")


