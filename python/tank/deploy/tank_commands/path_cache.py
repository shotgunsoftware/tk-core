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

from ...errors import TankError
from ... import path_cache

from .action_base import Action


class SynchronizePathCache(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "sync_folder_cache", 
                        Action.PC_LOCAL, 
                        ("Ensures that the local path cache is up to date with Shotgun."), 
                        "Folders")
    
    def run(self, log, args):
        
        if len(args) == 1 and args[1] == "--full":
            force = True
        
        elif len(args) == 0:
            force = False
            
        else:
            raise TankError("Syntax: sync_path_cache [--full]!")
        
        log.info("Ensuring the path cache file is up to date...")
        log.info("Will try to do an incremental sync. If you want to force a complete re-sync "
                 "to happen, run this command with a --full flag.")
        if force:
            log.info("Doing a full sync.")
            
        pc = path_cache.PathCache(self.tk)
        pc.synchronize(log, force)
        
        log.info("The path cache has been synchronized.")

class PathCacheMigrationAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "upgrade_folders", 
                        Action.PC_LOCAL, 
                        "Upgrades on old project to use the shared folder generation that was introduced in Toolkit 0.14", 
                        "Core Upgrade Related")
    
    def run(self, log, args):
        
        log.info("Placeholder contents")





class PathCacheInfoAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "folder_info", 
                        Action.GLOBAL, 
                        "Shows a breakdown of all the folders created for a particular entity.", 
                        "Folders")
    
    def run(self, log, args):
        
        log.info("Placeholder contents")

class DeleteFolderAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "delete_folder", 
                        Action.GLOBAL, 
                        ("Controls deletion of folders that represent Shotgun entities "
                         "such as Shots and Assets."), 
                        "Folders")
    
    def run(self, log, args):
        
        log.info("Placeholder contents")


class RenameFolderAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "rename_folder", 
                        Action.GLOBAL, 
                        ("Controls renaming of folders that represent Shotgun entities "
                         "such as Shots and Assets."), 
                        "Folders")
    
    def run(self, log, args):
        
        log.info("Placeholder contents")


