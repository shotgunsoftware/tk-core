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

from ...util.login import get_current_user 

from tank_vendor import yaml

import pprint
import os


class SynchronizePathCache(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "sync_folder_cache", 
                        Action.TK_INSTANCE, 
                        ("Ensures that the local path cache is up to date with Shotgun."), 
                        "Production")

        # this method can be executed via the API
        self.supports_api = True
        self.parameters = {}        
        self.parameters["full_sync"] = { "description": "Perform a full sync", "default": False, "type": "bool" }
        
    def run_noninteractive(self, log, parameters):
        """
        API accessor
        """
        # validate params and seed default values
        computed_params = self._validate_parameters(parameters)
        return self._run(log, computed_params["full_sync"])
    
    def run_interactive(self, log, args):
        """
        Tank command accessor
        """
        if len(args) == 1 and args[0] == "--full":
            force = True
        
        elif len(args) == 0:
            force = False
            
        else:
            raise TankError("Syntax: sync_path_cache [--full]")

        return self._run(log, force)
    
    
    def _run(self, log, force):
        """
        Actual business logic for command
        
        :param log: logger
        :param force: boolean flag to indicate that a full sync should be carried out
        """

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
                        Action.TK_INSTANCE, 
                        ("Upgrades on old project to use the shared folder "
                        "generation that was introduced in Toolkit 0.15"), 
                        "Admin")
    
    def run_interactive(self, log, args):
        
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
        
        os.chmod(pipe_config_sg_id_path, 0666)
        try:
            # and write the new file
            fh = open(pipe_config_sg_id_path, "wt")
            yaml.dump(curr_settings, fh)
        except Exception, exp:
            raise TankError("Could not write to pipeline configuration settings file %s. "
                            "Error reported: %s" % (pipe_config_sg_id_path, exp))
        finally:
            fh.close()                        
        
        # tell pipeline config object to reread settings...
        self.tk.pipeline_configuration.force_reread_settings()
        
        # and synchronize path cache
        log.info("Running folder synchronization...")
        pc = path_cache.PathCache(self.tk)
        try:
            pc.synchronize(log)
        finally:
            pc.close()
        
        log.info("All done! This project and pipeline configuration is now syncing its folders "
                 "with Shotgun.")






class UnregisterFoldersAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "unregister_folders", 
                        Action.CTX, 
                        ("Unregisters the folders for an object in Shotgun."), 
                        "Admin")
    
    def run_interactive(self, log, args):
        
        if self.context.entity is None:
            raise TankError("You need to specify a Shotgun entity - such as a Shot or Asset!")

        entity = self.context.entity

        pc = path_cache.PathCache(self.tk)
        try:
            pc.synchronize(log, force=False)
        finally:
            pc.close()
        
        sg_matches = self.tk.shotgun.find(path_cache.SHOTGUN_ENTITY, 
                                       [[path_cache.SG_ENTITY_FIELD, "is", entity]],
                                       ["id", path_cache.SG_PATH_FIELD])
        
        # now use the path cache to get a list of all folders (recursively) that are
        # linked up to the folders registered for this entity.
        
        paths = []
        pc = path_cache.PathCache(self.tk)
        try:
            for sg_match in sg_matches:
                paths.extend( pc.get_folder_tree_from_sg_id( sg_match["id"] ) )
        finally:
            pc.close()
        
        if len(paths) == 0:
            log.info("This entity does not have any folder associated!")
            return
        
        log.info("")
        log.info("The following folders are associated with %s %s:" % (entity["type"], entity["name"]))
        for p in paths:
            log.info(" - %s" % p["path"])
        
        log.info("")
        log.info("Proceeding would unregister the above paths from Toolkit's folder database. "
                 "This will not alter any of the content in the file system, but once you have "
                 "unregistered the paths, they will not be recognized by Shotgun.")
        log.info("")
        log.info("This is useful if you for example have renamed an Asset or Shot and want to "
                 "move the data around on disk. In this case, start by unregistering the existing "
                 "folder entries in Shotgun, then rename the Shot or Asset in Shotgun. Next, "
                 "create new folders on disk using Toolkit's 'create folders' command and lastly "
                 "move all your file system data across from the old location to the new location.")
        log.info("")
        val = raw_input("Proceed with unregister? (Yes/No) ? [Yes]: ")
        if val != "" and not val.lower().startswith("y"):
            log.info("Exiting! Nothing was unregistered.")
            return
        
        log.info("Removing items from Shotgun....")
        log.info("")
        
        sg_batch_data = []
        for p in paths:                            
            req = {"request_type":"delete", 
                   "entity_type": path_cache.SHOTGUN_ENTITY, 
                   "entity_id": p["sg_id"] }
            sg_batch_data.append(req)
        
        try:    
            response = self.tk.shotgun.batch(sg_batch_data)
        except Exception, e:
            raise TankError("Shotgun Reported an error. Please contact support. "
                            "Details: %s Data: %s" % (e, sg_batch_data))
        
        # now register the deleted ids in the event log
        # this will later on be read by the synchronization            
        # now, based on the entities we just deleted, assemble a metadata chunk that 
        # the sync calls can use later on.
        
        pc_link = {"type": "PipelineConfiguration",
                   "id": self.tk.pipeline_configuration.get_shotgun_id() }
        
        project_link = {"type": "Project", 
                        "id": self.tk.pipeline_configuration.get_project_id() }
        
        meta = {}
        # the api version used is always useful to know
        meta["core_api_version"] = self.tk.version
        # shotgun ids created
        meta["sg_folder_ids"] = [ x["sg_id"] for x in paths]
        
        sg_event_data = {}
        sg_event_data["event_type"] = "Toolkit_Folders_Delete"
        sg_event_data["description"] = "Toolkit %s: Unregistered %s folders." % (self.tk.version, len(paths))
        sg_event_data["project"] = project_link
        sg_event_data["entity"] = pc_link
        sg_event_data["meta"] = meta        
        sg_event_data["user"] = get_current_user(self.tk)
    
        try:
            self.tk.shotgun.create("EventLogEntry", sg_event_data)
        except Exception, e:
            raise TankError("Shotgun Reported an error. Please contact support. "
                            "Details: %s Data: %s" % (e, sg_event_data))
        
        # lastly, another sync
        pc = path_cache.PathCache(self.tk)
        try:
            pc.synchronize(log, force=False)
        finally:
            pc.close()

        log.info("")
        log.info("Unregister complete!")
        