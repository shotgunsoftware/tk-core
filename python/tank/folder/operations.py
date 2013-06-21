"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Main entry points for folder creation.

"""

import os
import sys

from .configuration import FolderConfiguration
from .folder_io import FolderIOReceiver
from .folder_types import EntityLinkTypeMismatch

from ..errors import TankError
from ..platform import constants


def create_single_folder_item(tk, config_obj, io_receiver, entity_type, entity_id, step_id, task_id, engine):
    """
    Creates folders for an entity type and an entity id.
    :param config_obj: a FolderConfiguration object representing the folder configuration
    :param io_receiver: a FolderIOReceiver representing the folder operation callbacks
    :param entity_type: Shotgun entity type
    :param entity_id: Shotgun entity id
    :param task_id: shotgun task id if this folder creation is associated with a particular task
    :param step_id: shotgun step id if this folder creation is associated with a particular step
    :param engine: Engine to create folders for / indicate second pass if not None.
    """
    # TODO: Confirm this entity exists and is in this project
    # Recurse over entire tree and find find all Entity folders of this type
    folder_objects = config_obj.get_folder_objs_for_entity_type(entity_type)
    # now we have folder objects representing the entity type we are after.
    # (for example there may be 3 SHOT nodes in the folder config tree)
    # For each folder, find the list of entities needed to build the full path and
    # ensure its parent folders exist. Then, create the folder for this entity with
    # all its children.
    for folder_obj in folder_objects:
        
        # fill in the information we know about this entity now
        entity_id_seed = { 
            entity_type: { "type": entity_type, "id": entity_id },
            "current_task_id": task_id,
            "current_step_id": step_id 
        }
        
        # now go from the folder object, deep inside the hierarchy,
        # up the tree and resolve all the entity ids that are required 
        # in order to create folders.
        try:
            shotgun_entity_data = folder_obj.extract_shotgun_data_upwards(tk.shotgun, entity_id_seed)
        except EntityLinkTypeMismatch:
            # the seed entity id object does not satisfy the link
            # path from folder_obj up to the root. 
            continue
        
        # now get all the parents, the list goes from the bottom up
        # parents:
        # [Entity /Project/sequences/Sequence/Shot, 
        #  Entity /Project/sequences/Sequence, 
        #  Static /Project/sequences, Project /Project ]
        #
        # the last element is now always the project object
        folder_objects_to_recurse = [folder_obj] + folder_obj.get_parents()
        
        # get the project object and take it out of the list
        # we will use the project object to start the recursion down
        project_folder = folder_objects_to_recurse.pop()
        
        # get the parent path of the project folder
        parent_project_path = os.path.abspath(os.path.join(project_folder.get_data_root(), ".."))
        
        # handle a special case for UNC paths and windows
        # if the project is \\server\share, the parent resolve above
        # will return \\server\share which is obviously wrong: we want it
        # to return \\server. Handle this case as a special case:
        if project_folder.get_data_root() == parent_project_path and sys.platform == "win32":
            
            # os.path.split does the trick:
            # >>> os.path.split("\\\\server\\share\\drive")
            # ('\\\\server\\share', 'drive')
            # >>> os.path.split("\\\\server\\share")
            # ('\\\\server', 'share')
            # >>> os.path.split("\\\\server\\share")
            parent_project_path = os.path.split(parent_project_path)[0]
        
        # now walk down, starting from the project level until we reach our entity 
        # and create all the structure.
        #
        # we pass a list of folder objects to create, so that in the case an object has multiple
        # children, the folder creation knows which object to create at that point.
        #
        # the shotgun_entity_data dictionary contains all the shotgun data needed in order to create
        # all the folders down this particular recursion path
        project_folder.create_folders(io_receiver, 
                                      parent_project_path, 
                                      shotgun_entity_data, 
                                      True,
                                      folder_objects_to_recurse,
                                      engine)
        



    
def process_filesystem_structure(tk, entity_type, entity_ids, preview, engine):    
    """
    Creates filesystem structure in Tank based on Shotgun and a schema config.
    Internal implementation.
    
    :param tk: A tank instance
    :param entity_type: A shotgun entity type to create folders for
    :param entity_ids: list of entity ids to process or a single entity id
    :param preview: enable dry run mode?
    :param engine: A string representation matching a level in the schema. Passing this
                   option indicates to the system that a second pass should be executed and all
                   which are marked as deferred are processed. Pass None for non-deferred mode.
                   The convention is to pass the name of the current engine, e.g 'tk-maya'.
    
    :returns: tuple: list of items processed
    
    """

    # check that engine is either a string or None
    if not (isinstance(engine, basestring) or engine is None):
        raise ValueError("engine parameter needs to be a string or None")


    # Ensure ids is a list
    if not isinstance(entity_ids, (list, tuple)):
        if isinstance(entity_ids, int):
            entity_ids = (entity_ids,)
        elif isinstance(entity_ids, str) and entity_ids.isdigit():
            entity_ids = (int(entity_ids),)
        else:
            raise ValueError("Parameter entity_ids was passed %s, accepted types are list, tuple and int.")
    
    if len(entity_ids) == 0:
        return


    # all things to create
    items = []

    #################################################################################
    #
    # Steps are not supported
    #
    if entity_type == "Step":
        raise TankError("Cannot create folders from Steps, only for entity types such as Shots, Assets etc.")
        
    #################################################################################
    #
    # Special handling of tasks. In the case of tasks, jump to the connected entity
    # note that this requires a shotgun query, and is therefore a performance hit. 
    #
    # Tasks with no entity associated will be ignored.
    #
    if entity_type == "Task":
        
        filters = ["id", "in"]
        filters.extend(entity_ids) # weird filter format here
        
        data = tk.shotgun.find(entity_type, [filters], ["entity", "step"])
        for sg_entry in data:
            if sg_entry["entity"]: # task may not be associated with an entity
                
                # get the current step
                step_id = None
                if sg_entry["step"]:
                    step_id = sg_entry["step"]["id"]

                items.append( { "type":    sg_entry["entity"]["type"], 
                                "id":      sg_entry["entity"]["id"], 
                                "step_id": step_id, 
                                "task_id": sg_entry["id"] } )
            
    else:
        # normal entities
        for i in entity_ids:
            items.append( { "type": entity_type, "id": i, "step_id": None, "task_id": None } )
        
    # create schema builder
    schema_cfg_folder = tk.pipeline_configuration.get_schema_config_location()   
    config = FolderConfiguration(tk, schema_cfg_folder)
    
    # create an object to receive all IO requests
    io_receiver = FolderIOReceiver(tk, preview)

    # now loop over all individual objects and create folders
    for i in items:        
        create_single_folder_item(tk, 
                                  config, 
                                  io_receiver, 
                                  i["type"], 
                                  i["id"], 
                                  i["step_id"],
                                  i["task_id"],
                                  engine)

    folders_created = io_receiver.execute_folder_creation()
    
    return folders_created
