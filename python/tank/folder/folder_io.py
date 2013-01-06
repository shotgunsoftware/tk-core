"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Methods and classes for generating folders based on the high level schema scaffold.

Known constraints:
 - won't allow the same entity type to appear more than once in the path. (ie Asset > Sub Asset)

"""

import os

from .. import root
from ..path_cache import PathCache
from ..errors import TankError
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
        self._computed_items = list()
        self._creation_history = list()
        self._path_cache = PathCache(tk.project_path)
        
    def get_computed_items(self):
        """
        Returns list of files and folders that have been computed by the folder creation
        """
        return self._computed_items
            
    def get_creation_history(self):
        return self._creation_history

        
    ####################################################################################
    # called by the folder classes
            
    def make_folder(self, path, metadata):
        """
        Calls make folder callback.
        """
        self._creation_history.append({'path':path,
                                       'metadata':metadata,
                                       'action':constants.CREATE_FOLDER_ACTION})
        
        self._computed_items.append(path)

        if not self._preview_mode:
            self._tk.execute_hook(constants.CREATE_FOLDERS_CORE_HOOK_NAME, path=path, sg_entity=None)
    
    
    def make_entity_folder(self, path, entity, metadata):
        """
        Creates an entity folder, including any cache entries
        the entity must be a dict with id, type and name
        """
    
#        if not self._preview_mode:            
#            existing_paths = self._path_cache.get_paths(entity_type, entity_id)
#            if path not in existing_paths:
#                # path not in cache yet - add it now!
#                self._path_cache.add_mapping(entity_type, entity_id, entity_name, path)
    
        self._creation_history.append({'path':path,
                                       'entity':entity,
                                       'metadata':metadata,
                                       'action':constants.CREATE_FOLDER_ACTION})
    
    
    
    def copy_file(self, src_path, target_path, metadata):
        """
        Calls copy file callback.
        """
        
        self._creation_history.append({'source_path':src_path,
                                       'target_path':target_path,
                                       'metadata':metadata,
                                       'action':constants.COPY_FILE_ACTION})  
        
        
        self._computed_items.append(target_path)
        if not self._preview_mode:
            self._tk.execute_hook(constants.COPY_FILE_CORE_HOOK_NAME, source_path=src_path, target_path=target_path)
            
    
    def prepare_project_root(self, root_path):
        
        
        if root_path != self._tk.project_path:
            # make tank config directories
            tank_dir = os.path.join(root_path, "tank")
            #self.make_folder(tank_dir)
            config_dir = os.path.join(root_path, "tank", "config")
            #self.make_folder(config_dir)
            # write primary path 
            root.write_primary_root(config_dir, self._tk.project_path)
        


