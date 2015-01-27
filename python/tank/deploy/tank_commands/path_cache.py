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
Methods relating to the path cache
"""

from ...errors import TankError
from ... import path_cache
from ... import folder 

from .action_base import Action
from ...util.login import get_current_user 



class SynchronizePathCache(Action):
    """
    Tank command to synchronize the local disk path cache 
    with the FilesystemLocation entity on disk.
    """    
    
    def __init__(self):
        """
        Constructor
        """
        Action.__init__(self, 
                        "synchronize_folders", 
                        Action.TK_INSTANCE, 
                        ("Ensures that the local folders and folder metadata is up to date with Shotgun."), 
                        "Admin")

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
            full_sync = True
        
        elif len(args) == 0:
            full_sync = False
            
        else:
            raise TankError("Syntax: synchronize_folders [--full]")

        return self._run(log, full_sync)
    
    
    def _run(self, log, full_sync):
        """
        Actual business logic for command
        
        :param log: logger
        :param full_sync: boolean flag to indicate that a full sync should be carried out
        """

        if self.tk.pipeline_configuration.get_shotgun_path_cache_enabled():
            
            log.info("Ensuring that the local folder representation is up to date...")
            
            if full_sync:
                log.info("Doing a full sync.")
            else:
                log.info("Will try to do an incremental sync. If you want to force a complete re-sync, "
                         "run this command with a --full flag.")
                
                
            folder.synchronize_folders(self.tk, full_sync, log)
                
            log.info("Local folder information has been synchronized.")
        
        else:
            # remote cache not turned on for this project
            log.error("Looks like this project doesn't synchronize its folders with Shotgun! "
                      "If you want to turn on synchronization for this project, run "
                      "the 'upgrade_folders' tank command.")


class PathCacheMigrationAction(Action):
    """
    Tank command for migrating an existing project to use the new FilesystemLocation
    based syncing. After the migration command has been executed, the project will get
    its shotgun path cache flag enabled and an initial sync is carried out.
    """
    
    def __init__(self):
        """
        Constructor
        """        
        Action.__init__(self, 
                        "upgrade_folders", 
                        Action.TK_INSTANCE, 
                        ("Upgrades on old project to use the shared folder "
                        "generation that was introduced in Toolkit 0.15"), 
                        "Admin")
    
    
    
    def run_interactive(self, log, args):
        """
        Tank command accessor
        """
                
        log.info("Welcome to the folder sync upgrade command!")
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
        log.info("")
        log.info("Note! If you have any cloned pipeline configurations for this project, you must run "
                 "'tank upgrade_folders' for each one of them in order for them to pick up folders "
                 "from Shotgun.")
        log.info("")
        val = raw_input("Turn on syncing for this pipeline configuration (Yes/No) ? [Yes]: ")
        if val != "" and not val.lower().startswith("y"):
            log.info("Exiting! Syncing will not be turned on.")
            return

        # first load up the current path cache file and make sure 
        # shotgun has got all those entries present as FilesystemLocations.
        log.info("")
        log.info("Phase 1/3: Pushing data from the current path cache to Shotgun...")
        curr_pc = path_cache.PathCache(self.tk)
        try:
            curr_pc.ensure_all_entries_are_in_shotgun(log)
        finally:
            curr_pc.close()        

        # now turn on the cloud based path cache. This means that from now on, a new path 
        # cache, stored on the local disk, will be used instead of the previous (shared) one.
        log.info("")
        log.info("Phase 2/3: Switching on the Shotgun Path Cache...")
        self.tk.pipeline_configuration.turn_on_shotgun_path_cache()
         
        # and synchronize path cache
        log.info("")
        log.info("Phase 3/3: Synchronizing your local machine with Shotgun...")
        pc = path_cache.PathCache(self.tk)
        try:
            pc.synchronize(log, full_sync=True)
        finally:
            pc.close()
        
        log.info("")
        log.info("All done! This project and pipeline configuration is now synchronizing its folders with Shotgun.")
        log.info("")
        log.info("Once all pipeline configurations for this project have been upgraded, the previous path cache "
                 "file, located in PROJECT_ROOT/tank/cache, is no longer needed and can be removed.")
        log.info("")
        log.info("")

class UnregisterFoldersAction(Action):
    """
    Tank command for unregistering a folder on disk from Shotgun. This is part of the process of
    the deletion of a folder on disk. As part of removing or moving, the folder needs to be 
    unregistered with Shotgun to ensure that the connection between that path and the related 
    entity is undone.
    """
    
    def __init__(self):
        """
        Constructor
        """        
        Action.__init__(self, 
                        "unregister_folders", 
                        Action.CTX, 
                        ("Unregisters the folders for an object in Shotgun."), 
                        "Admin")
    
    def run_interactive(self, log, args):
        """
        Tank command accessor
        """
        
        if not self.tk.pipeline_configuration.get_shotgun_path_cache_enabled():            
            # remote cache not turned on for this project
            log.error("Looks like this project doesn't synchronize its folders with Shotgun! "
                      "If you want to turn on synchronization for this project, run "
                      "the 'upgrade_folders' tank command.")
            return
        
        
        if self.context.entity is None:
            raise TankError("You need to specify a Shotgun entity - such as a Shot or Asset!")

        entity = self.context.entity

        pc = path_cache.PathCache(self.tk)
        try:
            pc.synchronize(log)
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
            raise TankError("Shotgun Reported an error while trying to write a Toolkit_Folders_Delete event "
                            "log entry after having successfully removed folders. Please contact support for "
                            "assistance. Error details: %s Data: %s" % (e, sg_event_data))
        
        # lastly, another sync
        pc = path_cache.PathCache(self.tk)
        try:
            pc.synchronize(log)
        finally:
            pc.close()

        log.info("")
        log.info("Unregister complete!")
        
