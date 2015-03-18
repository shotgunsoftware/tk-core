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
Method to unregister folders from the path cache
"""

from ...errors import TankError
from ... import path_cache
from .action_base import Action
from ...util.login import get_current_user 

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
                        Action.TK_INSTANCE, 
                        ("Unregisters the folders for an object in Shotgun."), 
                        "Admin")
        
        # this method can be executed via the API
        self.supports_api = True

        self.parameters = {}
        
        self.parameters["path"] = { "description": "Path to unregister. Any child paths will be unregistered too.",
                                    "default": None,
                                    "type": "str" }
        
        self.parameters["entity"] = { "description": ("Entity to unregister. Should be a Shotgun-style entity "
                                                      "dictionary with keys 'type' and 'id'."),
                                      "default": None,
                                      "type": "dict" }
        
    
    def run_interactive(self, log, args):
        """
        Tank command accessor
        
        :param log: Std logging object
        :param parameters: Std tank command parameters dict        
        """
        
        if not self.tk.pipeline_configuration.get_shotgun_path_cache_enabled():            
            # remote cache not turned on for this project
            log.error("Looks like this project doesn't synchronize its folders with Shotgun! "
                      "If you'd like to upgrade your path cache to turn on synchronization for "
                      "this project, run the 'tank upgrade_folders' command.")
            return
        
        # there are multiple syntaxes for this command
        # - context based: tank Shot ABC123 unregister_folders
        # - path based: tank unregister_folders path1, path2, path3
        
        if self.context.entity:
            # context based - e.g. 'tank Shot ABC123 unregister_folders' 
            self._unregister_entity(self.context.entity, log, prompt=True)
        
        else:
            # no context - so it is path based instead 
            if len(args) == 0:
                # display help message
                
                log.info("Unregister folders on your filesystem that are being tracked by Toolkit. "
                         "When applications are launched and folders are created on your filesystem, "
                         "new entries are stored in Shotgun as FilesystemLocation entities. These "
                         "records are called the 'path cache', and are used to track the relationship "
                         "between Shotgun entities and folders on disk. Use this command if you ever "
                         "need to remove these associations.")
                log.info("")
                log.info("Pass in a Shotgun entity (by name or id):")
                log.info("> tank Shot ABC123 unregister_folders")
                log.info("")
                log.info("Or pass in one or more paths:")
                log.info("> tank unregister_folders /path/to/folder_a /path/to/folder_b")
                log.info("")
                
            else:
                paths = args
                log.info("Unregistering the following folders:")
                for p in paths:
                    log.info(" - %s" % p)
                log.info("")
                self._unregister_paths(paths, log, prompt=True)
        
        
    def run_noninteractive(self, log, parameters):
        """
        API accessor
        
        :param log: Std logging object
        :param parameters: Std tank command parameters dict
        :returns: List of dictionaries to represents the items that were unregistered.
                  Each dictionary has keys path and sg_id.
                  Note that the shotgun ids returned will refer to retired objects in 
                  Shotgun rather than live ones.
        """
        # validate params and seed default values
        computed_params = self._validate_parameters(parameters) 
        
        # must have a path or an entity
        if computed_params["path"] is None and computed_params["entity"] is None:
            raise TankError("Must either specify a path or an entity!")
        # ... but not both
        if computed_params["path"] and computed_params["entity"]:
            raise TankError("Cannot specify both a path and an entity!")
            
        if computed_params["path"]:
            path = computed_params["path"]
            return self._unregister_paths([path], log, prompt=False)
        
        if computed_params["entity"]:
            entity = computed_params["entity"]
            if "id" not in entity:
                raise TankError("Entity dictionary does not contain an id key!")
            if "type" not in entity:
                raise TankError("Entity dictionary does not contain a type key!")
            return self._unregister_entity(entity, log, prompt=False)
            

    def _unregister_paths(self, paths, log, prompt):
        """
        Unregisters a path.
        
        :param paths: list of paths to unregister
        :param log: python logger
        :param prompt: Boolean to indicate that we can prompt the user for information or confirmation
        :returns: List of dictionaries to represents the items that were unregistered.
                  Each dictionary has keys path and sg_id.
                  Note that the shotgun ids returned will refer to retired objects in 
                  Shotgun rather than live ones.
        """
        log.debug("Will unregister folders for the following root paths:")
        for p in paths:
            log.debug(p)
        
        # first of all, make sure we are up to date.
        pc = path_cache.PathCache(self.tk)
        try:
            pc.synchronize(log)

            fs_location_ids = set()
            for p in paths:
                sg_id = pc.get_shotgun_id_from_path(p)
                if sg_id is None:
                    log.warning("Path '%s' is not registered in Shotgun - ignoring." % p)
                else:
                    log.debug("The path '%s' matches FilesystemLocation id: %s" % (p, sg_id))
                    fs_location_ids.add(sg_id)

        finally:
            pc.close()
        
        if len(fs_location_ids) == 0:
            log.info("")
            log.info("No valid paths found!")
            return []
        
        return self._unregister_filesystem_location_ids(list(fs_location_ids), log, prompt)                              

    
    def _unregister_entity(self, entity, log, prompt):
        """
        Unregisters an entity from the path cache in Shotgun.
        
        :param entity: Shotgun entity dict (e.g Shot or Asset) with keys type and id
        :param log: Logger
        :param prompt: If true, the command may prompt the user for confirmation
        :returns: List of dictionaries to represents the items that were unregistered.
                  Each dictionary has keys path and sg_id.
                  Note that the shotgun ids returned will refer to retired objects in 
                  Shotgun rather than live ones.
        """
        log.debug("Unregister folders for Shotgun Entity %s..." % entity)
    
        # first of all, make sure we are up to date.
        pc = path_cache.PathCache(self.tk)
        try:
            pc.synchronize(log)
        finally:
            pc.close()

        # get the filesystem location ids which are associated with the entity    
        sg_data = self.tk.shotgun.find(path_cache.SHOTGUN_ENTITY, [[path_cache.SG_ENTITY_FIELD, "is", entity]])
        sg_ids = [x["id"] for x in sg_data]
        log.debug("The following path cache ids are linked to the entity: %s" % sg_ids)
        
        if len(sg_ids) == 0:
            log.info("This entity does not have any folder associated!")
            return []
        
        return self._unregister_filesystem_location_ids(sg_ids, log, prompt)                              
        
        
    def _unregister_filesystem_location_ids(self, ids, log, prompt):
        """
        Performs the unregistration of a path from the path cache database.
        Will recursively unregister any child items parented to the given
        filesystem location id.
        
        :param ids: List of filesystem location ids to unregister
        :param prompt: Should the user be presented with confirmation prompts?
        :param log: Logging instance
        :returns: List of dictionaries to represents the items that were unregistered.
                  Each dictionary has keys path and sg_id.
                  Note that the shotgun ids returned will refer to retired objects in 
                  Shotgun rather than live ones.
        """
        # now use the path cache to get a list of all folders (recursively) that are
        # linked up to the folders registered for this entity.
        
        paths = []
        pc = path_cache.PathCache(self.tk)
        try:
            for sg_fs_id in ids:
                paths.extend(pc.get_folder_tree_from_sg_id(sg_fs_id))
        finally:
            pc.close()
                
        log.info("")
        log.info("The following folders will be unregistered:")
        for p in paths:
            log.info(" - %s" % p["path"])
        
        log.info("")
        log.info("Proceeding will unregister the above paths from Toolkit's path cache. "
                 "This will not alter any of the content in the file system, but once you have "
                 "unregistered the paths, they will not be recognized by Shotgun util you run "
                 "Toolkit folder creation again.")
        log.info("")
        log.info("This is useful if you have renamed an Asset or Shot and want to move its "
                 "files to a new location on disk. In this case, start by unregistering the "
                 "folders for the entity, then rename the Shot or Asset in Shotgun. "
                 "Next, create new folders on disk using Toolkit's 'create folders' "
                 "command. Finally, move the files to the new location on disk.")
        log.info("")
        if prompt:
            val = raw_input("Proceed with unregistering the above folders? (Yes/No) ? [Yes]: ")
            if val != "" and not val.lower().startswith("y"):
                log.info("Exiting! Nothing was unregistered.")
                return []
        
        log.info("Unregistering folders from Shotgun...")
        log.info("")
        
        sg_batch_data = []
        for p in paths:                            
            req = {"request_type":"delete", 
                   "entity_type": path_cache.SHOTGUN_ENTITY, 
                   "entity_id": p["sg_id"] }
            sg_batch_data.append(req)
        
        try:    
            self.tk.shotgun.batch(sg_batch_data)
        except Exception, e:
            raise TankError("Shotgun reported an error while attempting to delete FilesystemLocation entities. "
                            "Please contact support. Details: %s Data: %s" % (e, sg_batch_data))
        
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
        
        return paths
        
