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
Methods and classes for generating folders based on the high level schema scaffold.

Known constraints:
 - won't allow the same entity type to appear more than once in the path. (ie Asset > Sub Asset)

"""

import os

from ..platform import constants
from ..errors import TankError

from ..path_cache import PathCache
    


class FolderIOReceiver(object):
    """
    Class that encapsulates all the IO operations from the various folder classes.
    """
    
    def __init__(self, tk, preview):
        """
        Constructor
        """
        self._tk = tk
        self._preview_mode = preview
        self._items = list()
        self._secondary_cache_entries = list()
        self._path_cache = PathCache(tk.pipeline_configuration)
        
    ####################################################################################
    # internal methods
        
    def _validate_folder(self, path, entity_type, entity_id, entity_name):
        """
        Consistency checks happening prior to folder creation. May raise a TankError
        if an inconsistency is detected.
        
        :param path: The path calculated
        :param entity_type: The entity type to associate with the path
        :param entity_id: The entity id to associate with the path
        :param entity_name: The name for the entity to associate with the name 
        """
    
        # Check 1. make sure that there isn't already a record with the same
        # name in the database and file system. If this is the case, and this record
        # has since been deleted, remove it from the database and proceed with the processing.
        # Use Case: Shot ABC is created. Folders are created. Shot is then deleted in Shotgun
        # Shot is then recreated in Shotgun and folder creation is executed. The old ABC
        # folder should now "link" up with the new ABC shot instead.
        entity_in_db = self._path_cache.get_entity(path)
        if entity_in_db is not None:
            # found a match in the path db!
            if entity_in_db["id"] != entity_id or entity_in_db["type"] != entity_type:
                
                # there is already a record in the database for this path,
                # but associated with another entity! Display an error message
                # and ask that the user investigates using special tank commands
    
                msg =  "Folder creation aborted! No folders have been created. "
                msg += "The path '%s' cannot be processed because it is already associated " % path
                msg += "with %s '%s' (id %s) in Shotgun. " % (entity_in_db["id"], entity_in_db["type"], entity_in_db["name"])
                msg += "You are now trying to associate it with %s '%s' (id %s). " % (entity_type, entity_id, entity_name)
                msg += "Please run the command 'tank check_folders %s %s' " % (entity_type, entity_id)
                msg += "to get a more detailed overview of why you are getting this message "
                msg += "and what you can do to resolve this situation."
                raise TankError(msg)
                
        # Check 2. Check if a folder for this shot has already been created,
        # but with another name. This can happen if someone
        # - creates a shot AAA
        # - creates folders on disk for Shot AAA
        # - renamed the shot to BBB
        # - tries to create folders. Now we don't want to create folders for BBB,
        #   since we already have a location on disk for this shot. 
        #
        # note: this can also happen if the folder creation rules change.
    
        for p in self._path_cache.get_paths(entity_type, entity_id, primary_only=False):
            # so we got a path that matches our entity
            if p != path and os.path.dirname(p) == os.path.dirname(path):
                # this path is identical to our path we are about to create except for the name. 
                # there is still a folder on disk. Abort folder creation
                # with a descriptive error message
                msg = "Folder creation aborted! No folders have been created. "
                msg += "The path '%s' cannot be created because another " % path
                msg += "path '%s' is already associated with %s %s. " % (p, entity_type, entity_name)
                msg += "This typically happens if an item in Shotgun is renamed or "
                msg += "if the path naming in the folder creation configuration "
                msg += "is changed. "
                msg += "Please run the command 'tank check_folders %s %s' " % (entity_type, entity_id)
                msg += "to get a more detailed overview of why you are getting this message "
                msg += "and what you can do to resolve this situation."
                
                raise TankError(msg)
    
    
    ####################################################################################
    # methods to call to actually execute the folder creation logic
        
    def execute_folder_creation(self):
        """
        Runs the actual execution. Returns a list of paths
        which were calculated to be created.
        """
        
        # request that the path cache is synced against shotgun
        self._path_cache.synchronize()        
        
        # do some pre processing to properly cover some edge cases   
        for i in self._items:

            if i.get("action") == "entity_folder":
                
                path = i.get("path")
                entity_type = i.get("entity").get("type")
                entity_id = i.get("entity").get("id")
                entity_name = i.get("entity").get("name")
                
                self._validate_folder(path, entity_type, entity_id, entity_name)
                                
        # now request the IO operations to take place
        created_folders = self._tk.execute_hook(constants.PROCESS_FOLDER_CREATION_HOOK_NAME, 
                                                items=self._items, 
                                                preview_mode=self._preview_mode)
        
        # now handle the path cache
        if not self._preview_mode:    

            entries = []
            
            for i in self._items:
                if i.get("action") == "entity_folder":
                    path = i.get("path")
                    entity = i.get("entity")
                    entries.append( {"entity": entity, "path": path, "primary": True} )
                    
            for i in self._secondary_cache_entries:
                path = i.get("path")
                entity = i.get("entity")
                entries.append( {"entity": entity, "path": path, "primary": False} )
                
            # register with path cache / shotgun
            self._path_cache.add_mappings(entries)


        # note that for backwards compatibility, we are returning all folders, not 
        # just the ones that were created
        folders = list()
        for i in self._items:
            action = i.get("action")
            if action in ["entity_folder", "create_file", "folder"]:
                folders.append( i["path"] )
            elif action == "copy":
                folders.append( i["target_path"] )        

        return folders
            
        
    ####################################################################################
    # methods called by the folder classes
            
    def register_secondary_entity(self, path, entity):
        """
        Called when a secondary entity is registered. A secondary
        entity is when a path contains more than one entity association.
        For example, a Shot folder configured to use the name
        {code}_{sg_sequence.Sequence.code} is implicity also linked
        to the associated sequence entity. This is the secondary entity.
        """
        self._secondary_cache_entries.append({"path": path, "entity": entity})
            
    def make_folder(self, path, metadata):
        """
        Called by the folder creation classes when a normal simple folder
        is to be created.
        """
        self._items.append({"path": path, "metadata": metadata, "action": "folder"})
    
    def make_entity_folder(self, path, entity, metadata):
        """
        Creates an entity folder, including any cache entries
        the entity parameter must be a dict with id, type and name.
        """
        self._items.append({"path": path, 
                            "metadata": metadata, 
                            "entity": entity, 
                            "action": "entity_folder"})
    
    def copy_file(self, src_path, target_path, metadata):
        """
        Called by the folder creation classes when a file is to be copied.
        """
        self._items.append({"source_path": src_path, 
                            "target_path": target_path, 
                            "metadata": metadata, 
                            "action": "copy"})              



