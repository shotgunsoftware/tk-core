"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Methods and classes for generating folders based on the high level schema scaffold.

Known constraints:
 - won't allow the same entity type to appear more than once in the path. (ie Asset > Sub Asset)

"""

import os

from tank_vendor import yaml

from .. import root
from ..path_cache import PathCache
from ..platform import constants
from ..errors import TankError

    


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
        self._path_cache = PathCache(tk.project_path)
        
    def execute_folder_creation(self):
        """
        Runs the actual execution. Returns a list of paths
        which were calculated to be created.
        """
        
        # first we do some pre processing to properly cover some edge cases   
        if not self._preview_mode:
                 
            for i in self._items:

                if i.get("action") == "entity_folder":
                    
                    path = i.get("path")
                    entity_type = i.get("entity").get("type")
                    entity_id = i.get("entity").get("id")
                    entity_name = i.get("entity").get("name")
                    
                    folder_preflight_checks(self._tk, 
                                            self._path_cache, 
                                            path, 
                                            entity_type, 
                                            entity_id, 
                                            entity_name)
                                
        # now request the IO operations to take place
        created_folders = self._tk.execute_hook(constants.PROCESS_FOLDER_CREATION_HOOK_NAME, 
                                                items=self._items, 
                                                preview_mode=self._preview_mode)
        
        # now handle the path cache
        if not self._preview_mode:    
            for i in self._items:
                if i.get("action") == "entity_folder":
                    path = i.get("path")
                    entity_type = i.get("entity").get("type")
                    entity_id = i.get("entity").get("id")
                    entity_name = i.get("entity").get("name")
                    self._path_cache.add_mapping(entity_type, entity_id, entity_name, path)
                    
            for i in self._secondary_cache_entries:
                path = i.get("path")
                entity_type = i.get("entity").get("type")
                entity_id = i.get("entity").get("id")
                entity_name = i.get("entity").get("name")
                self._path_cache.add_mapping(entity_type, entity_id, entity_name, path, False)


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
    
    def prepare_project_root(self, root_path, metadata):
        """
        Called when the project root is created.
        """
        if root_path != self._tk.project_path:
            
            # this is one of those non-primary project roots
            # used when there are multiple roots configured
            # ensure that we have a primary_project.yml file
            primary_roots_file = os.path.join(root_path, "tank", "config", "primary_project.yml")

            # get the content for this file
            primary_roots_content = root.platform_paths_for_root("primary", self._tk.project_path)
            
            # and translate that into yaml
            primary_roots_content_yaml = yaml.dump(primary_roots_content)
                        
            self._items.append({"path": primary_roots_file, 
                                "metadata": metadata, 
                                "action": "create_file",
                                "content": primary_roots_content_yaml})
            



def folder_preflight_checks(tk, path_cache, path, entity_type, entity_id, entity_name):
    """
    Consistency checks happening prior to folder creation and ultimately
    insertion into the path cache
    """
    # 1. make sure that there isn't already a record with the same
    # name in the database and file system. If this is the case, and this record
    # has since been deleted, remove it from the database and proceed with the processing.
    # Use Case: Shot ABC is created. Folders are created. Shot is then deleted in Shotgun
    # Shot is then recreated in Shotgun and folder creation is executed. The old ABC
    # folder should now "link" up with the new ABC shot instead.
    entity_in_db = path_cache.get_entity(path)
    if entity_in_db is not None:
        # found a match in the path db!
        if entity_in_db["id"] != entity_id or entity_in_db["type"] != entity_type:
            # there is already a record in the database for this path,
            # but associated with another entity!
            
            # if that entity is retired, then delete the entry from the db
            sg_data = tk.shotgun.find_one(entity_in_db["type"], [["id", "is", entity_in_db["id"]]])
            if sg_data is None:
                # could not find this in shotgun! means that it was retired.
                # so delete it from the path cache too. This will delete all 
                # entries in the path cache that are associated with the path.
                path_cache.delete_path_tree(path)

    # 2. make sure that we clear out any entries that are old. Basically,
    # if someone has created a shot ABC on disk, then renamed it to ABD,
    # then renamed the folder from /foo/ABC to /foo/ABD, we want to clear
    # out the original entry for this record, which was pointing at /foo/ABC.
    for p in path_cache.get_paths(entity_type, entity_id, primary_only=False):
        # so we got a path that matches our entity
        if p != path and os.path.dirname(p) == os.path.dirname(path):
            # this path is identical to our path we are about to create
            # except for the name. 
            if not os.path.exists(p):
                # the path in the database has been deleted from disk,
                # delete the record from the path cache
                path_cache.delete_path_tree(p)
            
            else:
                # there is still a folder on disk. Abort folder creation
                # with a descriptive error message
                msg = "Folder creation aborted! No folders have been created. "
                msg += "The path '%s' cannot be created because another " % path
                msg += "path '%s' is already associated with %s %s. " % (p, entity_type, entity_name)
                msg += "This typically happens if an item in Shotgun is renamed or "
                msg += "if the path naming in the folder creation configuration "
                msg += "is changed. To resolve this problem, either revert the name "
                msg += "changes in Shotgun or move the folder '%s' to '%s' " % (p, path)
                msg += "and run the folder creation again."
                raise TankError(msg)
