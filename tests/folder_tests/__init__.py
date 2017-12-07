

import os
import unittest
import shutil
from mock import Mock, patch
import tank
from tank_vendor import yaml
from tank import TankError
from tank import hook
from tank import folder
from tank.path_cache import PathCache
from tank_test.tank_test_base import *

###############################################################################################
# useful methods for folder creation tests.

g_paths_created = []

def assert_paths_to_create(expected_paths):
    """
    No file system operations are performed.
    """
    # Check paths sent to make_folder
    for expected_path in expected_paths:
        if expected_path not in g_paths_created:
            msg = "\n------------------\n"
            msg += "Expected path \n%s\nnot found in paths created on disk:\n\n" % expected_path
            msg += "\n".join(g_paths_created)
            msg += "\n------------------\n"
            assert False, msg
    for actual_path in g_paths_created:
        if actual_path not in expected_paths:
            msg = "\n------------------\n"
            msg += "Unexpected path \n%s\ncreated by system.\n\n" % actual_path
            msg += "List of paths created on disk:\n"
            msg += "\n".join(g_paths_created)
            msg += "\nList of paths expected to be created:\n"
            msg += "\n".join(expected_paths)
            msg += "------------------\n"
            assert False, msg




def execute_folder_creation_proxy(self):
    """
    Runs the actual folder execution. 
    
    :returns: A list of paths which were calculated to be created
    """

    path_cache = PathCache(self._tk)
    
    try:
        # because the sync can make changes to the path cache, do not run in preview mode
        remote_items = []
        if not self._preview_mode: 
            
            # request that the path cache is synced against shotgun
            # new items that were not locally available are returned
            # as a list of dicts with keys id, type, name, configuration and path
            rd = path_cache.synchronize()
            
            # for each item we get back from the path cache synchronization,
            # issue a remote entity folder request and pass that down to 
            # the folder creation hook. This way, folders can be auto created
            # across multiple locations if desirable.            
            for i in rd:
                remote_items.append( {"action": "remote_entity_folder",
                                      "path": i["path"],
                                      "metadata": i["metadata"],
                                      "entity": i["entity"] })
    
        # put together a list of entries we should pass to the database
        db_entries = []
        
        for i in self._items:
            if i.get("action") == "entity_folder":
                db_entries.append( {"entity": i["entity"], 
                                    "path": i["path"], 
                                    "primary": True, 
                                    "metadata": i["metadata"]} )
                
        for i in self._secondary_cache_entries:
            db_entries.append( {"entity": i["entity"], 
                                "path": i["path"], 
                                "primary": False, 
                                "metadata": i["metadata"]} )
        
        
        
        # now that we are synced up with all remote sites,
        # validate the data before we push it into the databse. 
        # to properly cover some edge cases        
        try:
            path_cache.validate_mappings(db_entries)
        except TankError as e:                
            # ok folders created for synced stuff. Now re-raise validation error
            raise TankError("Folder creation aborted: %s" % e) 
        
        
        # validation passed!
        # now request the IO operations to take place
        # note that we pass both the items that were created from syncing with remote
        # and the new folders that have been computed
        
        folder_creation_items = remote_items + self._items
                    
        # database data was validated, folders on disk created
        # finally store all our new data in the path cache and in shotgun
        if not self._preview_mode:
            path_cache.add_mappings(db_entries, self._entity_type, self._entity_ids)

        # return all folders that were computed 
        folders = []
        for i in folder_creation_items:
            action = i.get("action")
            if action in ["entity_folder", "create_file", "folder", "remote_entity_folder"]:
                folders.append( i["path"] )
            elif action == "copy":
                folders.append( i["target_path"] )        

    finally:
        path_cache.close()

    global g_paths_created
    g_paths_created = folders

    return folders





