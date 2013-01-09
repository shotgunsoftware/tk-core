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
        self._path_cache = PathCache(tk.project_path)
        
    def execute_folder_creation(self):
        """
        Runs the actual execution. Returns a list of paths
        which were calculated to be created.
        """
        
        # now handle the path cache
        
        folders = self._tk.execute_hook(constants.PROCESS_FOLDER_CREATION_HOOK_NAME, 
                                        items=self._items, 
                                        preview_mode=self._preview_mode)
        
        if not self._preview_mode:    
            for i in self._items:
                if i.get("action") == "entity_folder":
                    path = i.get("path")
                    entity_type = i.get("entity").get("type")
                    entity_id = i.get("entity").get("id")
                    entity_name = i.get("entity").get("name")
                    
                    existing_paths = self._path_cache.get_paths(entity_type, entity_id)
                    if path not in existing_paths:
                        # path not in cache yet - add it now!
                        self._path_cache.add_mapping(entity_type, entity_id, entity_name, path)

        return folders
            
        
    ####################################################################################
    # methods called by the folder classes
            
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
            
