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
from ... import pipelineconfig

from .action_base import Action

from tank_vendor import yaml

import pprint
import os


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
        
        if self.tk.pipeline_configuration.get_shotgun_path_cache_enabled():
            log.info("Ensuring the path cache file is up to date...")
            log.info("Will try to do an incremental sync. If you want to force a complete re-sync "
                     "to happen, run this command with a --full flag.")
            if force:
                log.info("Doing a full sync.")
                
            pc = path_cache.PathCache(self.tk)
            pc.synchronize(log, force)
            pc.close()
            
            log.info("The path cache has been synchronized.")
        
        else:
            # remote cache not turned on for this project
            log.info("Looks like this project doesn't synchronize its folders with Shotgun! "
                     "If you want to turn on synchronization for this project, run "
                     "the 'upgrade_folders' tank command.")

class PathCacheMigrationAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "upgrade_folders", 
                        Action.PC_LOCAL, 
                        "Upgrades on old project to use the shared folder generation that was introduced in Toolkit 0.14", 
                        "Core Upgrade Related")
    
    def run(self, log, args):
        
        log.info("Welome to the folder sync upgrade command!")
        log.info("")
        log.info("Projects created with Toolkit v0.14 and earlier do not automatically synchronize "
                 "their folders on disk with Shotgun. You can use this command to turn on that folder "
                 "sync.")
        log.info("")
        
        if self.tk.pipeline_configuration.get_shotgun_path_cache_enabled():
            log.info("Looks like syncing is already turned on! Nothing to do!")
            return
        
        log.info("Turning on folder sync will first do a full synchronization of the "
                 "existing folders. After that, syncing will happen incrementally in the "
                 "background.")
        val = raw_input("Turn on syncing for this pipeline configuration (Yes/No) ? [Yes]: ")
        if val != "" and not val.lower().startswith("y"):
            log.info("Exiting! Syncing will not be turned on.")
            return
        
        log.info("")
        log.info("Configuring settings...")
        
        curr_pc_path = self.tk.pipeline_configuration.get_path()
        
        # get current settings
        curr_settings = pipelineconfig.get_pc_disk_metadata( curr_pc_path )
        log.debug("Current settings: %s" % pprint.pformat(curr_settings))
        
        # add path cache setting
        curr_settings["use_shotgun_path_cache"] = True
        
        # write the record to disk
        pipe_config_sg_id_path = os.path.join(curr_pc_path, "config", "core", "pipeline_configuration.yml")
        log.debug("New settings: %s" % pprint.pformat(curr_settings))
        log.debug("Writing to pc cache file %s" % pipe_config_sg_id_path)        
        
        try:
            fh = open(pipe_config_sg_id_path, "wt")
            yaml.dump(curr_settings, fh)
            fh.close()
        except Exception, exp:
            raise TankError("Could not write to pipeline configuration cache file %s. "
                            "Error reported: %s" % (pipe_config_sg_id_path, exp))
        
        # tell pipeline config object to reread settings...
        self.tk.pipeline_configuration.force_reread_settings()
        
        # and synchronize path cache
        log.info("Running folder synchronization...")
        pc = path_cache.PathCache(self.tk)
        pc.synchronize(log)
        pc.close()
        
        log.info("All done! This project and pipeline configuration is now syncing its folders "
                 "with Shotgun.")




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


