"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Methods and classes for generating folders based on the high level schema scaffold.

Known constraints:
 - won't allow the same entity type to appear more than once in the path. (ie Asset > Sub Asset)

"""

import os
import re
import copy
import fnmatch

from .folder import Static, ListField, Entity, Project, UserWorkspace, EntityLinkTypeMismatch

from .. import root
from ..path_cache import PathCache
from ..errors import TankError
from ..platform import constants

from tank_vendor import yaml


class FolderConfiguration(object):
    """
    Class that loads the schema from disk and constructs folder objects.
    """
    
    def __init__(self, tk, schema_config_path):
        """
        Constructor
        """
        self._tk = tk
        # access shotgun nodes by their entity_type
        self._entity_nodes_by_type = {}
        # read skip files config
        self._ignore_files = self._read_ignore_files(schema_config_path)
        # load schema
        self._load_schema(schema_config_path)
        

    ##########################################################################################
    # public methods

    def get_folder_objs_for_entity_type(self, entity_type):
        """
        Returns all the nodes representing a particular sg entity type 
        """
        return self._entity_nodes_by_type.get(entity_type)


    ####################################################################################
    # utility methods
    
    def _directory_paths(self, parent_path):
        """
        Returns all the directories for a given path
        """
        directory_paths = []
        for file_name in os.listdir(parent_path):
            full_path = os.path.join(parent_path, file_name)
            # ignore files
            if os.path.isdir(full_path) and not file_name.startswith("."):
                directory_paths.append(full_path)
        return directory_paths

    def _file_paths(self, parent_path):
        """
        Returns all the files for a given path except yml files
        Also ignores any files mentioned in the ignore files list
        """
        file_paths = []
        for file_name in os.listdir(parent_path):

            # don't process files matching ignore pattern(s)
            if not any(fnmatch.fnmatch(file_name, p) for p in self._ignore_files):

                full_path = os.path.join(parent_path, file_name)
                # yml files - those are our config files
                if os.path.isfile(full_path) and not full_path.endswith(".yml"):
                    file_paths.append(full_path)

        return file_paths
                    
    def _read_metadata(self, full_path):
        """
        Reads metadata file.

        :param full_path: Absolute path without extension
        :returns: Dictionary of file contents or None
        """
        metadata = None
        # check if there is a yml file with the same name
        yml_file = "%s.yml" % full_path
        if os.path.exists(yml_file):
            # try to parse it
            try:
                open_file = open(yml_file)
                try:
                    metadata = yaml.load(open_file)
                finally:
                    open_file.close()
            except Exception, error:
                raise TankError("Cannot load config file '%s'. Error: %s" % (yml_file, error))
        return metadata
    

    def _read_ignore_files(self, schema_config_path):
        """
        Reads ignore_files from root of schema if it exists.
        Returns a list of patterns to ignore.
        """
        ignore_files = []
        file_path = os.path.join(schema_config_path, "ignore_files")
        if os.path.exists(file_path):
            open_file = open(file_path, "r")
            try:
                for line in open_file.readlines():
                    # skip comments
                    if "#" in line:
                        line = line[:line.index("#")]
                    line = line.strip()
                    if line:
                        ignore_files.append(line)
            finally:
                open_file.close()
        return ignore_files

    ##########################################################################################
    # internal stuff


    def _load_schema(self, schema_config_path):
        """
        Scan the config and build objects structure
        """
                
        project_dirs = self._directory_paths(schema_config_path)
        
        # make some space in our obj/entity type mapping
        self._entity_nodes_by_type["Project"] = []
        
        if len(project_dirs) == 1:
            # Only one project root - in this case, this single root needs to be named
            # 'project' for backwards compatibility reasons and it represents the 
            # project name in shotgun
            project_root = os.path.join(schema_config_path, "project")
            
            if not os.path.exists(project_root):
                raise TankError("When running Tank in a single-root configuration, a folder "
                                "named 'project' needs to be present in %s. This folder "
                                "represents the current Shotgun project." % schema_config_path)                
             
            # make root node
            project_obj = Project.create(self._tk, project_root, {}, self._tk.project_path)
            
            # store it in our lookup tables
            self._entity_nodes_by_type["Project"].append(project_obj)
             
            # recursively process the rest
            self._process_config_r(project_obj, project_root)
        
        elif len(project_dirs) > 1:
            # Multiple project roots - now you can arbitrary name things.
            
            roots = root.get_project_roots(self._tk.project_path)
            for project_dir in project_dirs:
                project_root = os.path.join(schema_config_path, project_dir)
                
                # read metadata to determine root path 
                metadata = self._read_metadata(project_root)
                if metadata:
                    if metadata.get("type", None) != "project":
                        raise TankError("Only items of type 'project' are allowed at the root level: %s" % project_root)
                    root_name = metadata.get("root_name", None)
                    if root_name is None:
                        raise TankError("Missing or invalid value for 'root_name' in metadata: %s" % project_root)

                    root_path = roots.get(root_name, None)
                    if root_path is None:
                        raise TankError("No path is specified for root %s" % root_name)
                else:
                    raise TankError("Project directory missing required metadata file: %s" % project_root)
                
                project_obj = Project.create(self._tk, project_root, metadata, root_path)

                # store it in our lookup tables
                self._entity_nodes_by_type["Project"].append(project_obj)
                
                # recursively process the rest
                self._process_config_r(project_obj, project_root)
        else:
            raise TankError("Could not find a project root folder in %s!" % schema_config_path)
        

    def _process_config_r(self, parent_node, parent_path):
        """
        Recursively scan the file system and construct an object
        hierarchy. 
        
        Factory method for Folder objects.
        """
        for full_path in self._directory_paths(parent_path):
            # check for metadata (non-static folder)
            metadata = self._read_metadata(full_path)
            if metadata:
                node_type = metadata.get("type", "undefined")
                
                if node_type == "shotgun_entity":
                    cur_node = Entity.create(self._tk, parent_node, full_path, metadata)
                    
                    # put it into our list where we group entity nodes by entity type
                    et = cur_node.get_entity_type()
                    if et not in self._entity_nodes_by_type:
                        self._entity_nodes_by_type[et] = []
                    self._entity_nodes_by_type[et].append(cur_node)
                    
                elif node_type == "shotgun_list_field":
                    cur_node = ListField.create(self._tk, parent_node, full_path, metadata)
                    
                elif node_type == "static":
                    cur_node = Static.create(self._tk, parent_node, full_path, metadata)     
                
                elif node_type == "user_workspace":
                    cur_node = UserWorkspace.create(self._tk, parent_node, full_path, metadata)     
                
                else:
                    # don't know this metadata
                    raise TankError("Error in %s. Unknown metadata type '%s'" % (full_path, node_type))
            else:
                # no metadata - so this is just a static folder!
                cur_node = Static.create(self._tk, parent_node, full_path, {})

            # and process children
            self._process_config_r(cur_node, full_path)
           
        # now process all files and add them to the parent_node token
        for f in self._file_paths(parent_path):
            parent_node.add_file(f)

    
    













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
    # post processing
    
        
    ####################################################################################
    # called by the folder classes
        
    def add_entry_to_cache_db(self, path, entity_type, entity_id, entity_name):
        """
        Adds entity to database. 
        """
        if not self._preview_mode:            
            existing_paths = self._path_cache.get_paths(entity_type, entity_id)
            if path not in existing_paths:
                # path not in cache yet - add it now!
                self._path_cache.add_mapping(entity_type, entity_id, entity_name, path)
    
    def _add_create_history(self, path, entity, metadata):
        self.creation_history.append({'path':path,
                                      'entity':entity,
                                      'metadata':metadata,
                                      'action':constants.CREATE_FOLDER_ACTION})

    def _add_copy_history(self, src_path, target_path, metadata):
        self.creation_history.append({'source_path':src_path,
                                      'target_path':target_path,
                                      'metadata':metadata,
                                      'action':constants.COPY_FILE_ACTION})  

    def make_folder(self, path, entity=None, metadata=None):
        """
        Calls make folder callback.
        """
        self._add_create_history(path, entity, metadata)
        self._computed_items.append(path)
        if not self._preview_mode:
            self._tk.execute_hook(constants.CREATE_FOLDERS_CORE_HOOK_NAME, path=path, sg_entity=None)
    
    def copy_file(self, src_path, target_path, metadata):
        """
        Calls copy file callback.
        """
        self._add_copy_history(src_path, target_path, metadata)
        self._computed_items.append(target_path)
        if not self._preview_mode:
            self._tk.execute_hook(constants.COPY_FILE_CORE_HOOK_NAME, source_path=src_path, target_path=target_path)
            
    
    def prepare_project_root(self, root_path):
        
        if root_path != self._tk.project_path:
            # make tank config directories
            tank_dir = os.path.join(root_path, "tank")
            self.make_folder(tank_dir)
            config_dir = os.path.join(root_path, "tank", "config")
            self.make_folder(config_dir)
            # write primary path 
            root.write_primary_root(config_dir, self._tk.project_path)
        


################################################################################################
# public functions

def create_single_folder_item(tk, config_obj, io_receiver, entity_type, entity_id, engine):
    """
    Creates folders for an entity type and an entity id.
    :param config_obj: a FolderConfiguration object representing the folder configuration
    :param io_receiver: a FolderIOReceiver representing the folder operation callbacks
    :param entity_type: Shotgun entity type
    :param entity_id: Shotgun entity id
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
            entity_type: { "type": entity_type, "id": entity_id }
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
    
    :returns: tuple: (How many entity folders were processed, list of items)
    
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


    tk.execute_hook(constants.PRE_PROCESS_FOLDER_CREATION_HOOK_NAME, 
                    entity_type=entity_type, 
                    entity_ids=entity_ids, 
                    preview=preview, 
                    engine=engine)

    # all things to create, organized by type
    items = {}

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
        
        data = tk.shotgun.find(entity_type, [filters], ["entity"])
        for sg_entry in data:
            if sg_entry["entity"]: # task may not be associated with an entity
                entry_type = sg_entry["entity"]["type"]
                if entry_type not in items:
                    items[entry_type] = []
                items[entry_type].append(sg_entry["entity"]["id"])
            
    else:
        # normal entities
        items[entity_type] = entity_ids

    
    # create schema builder
    schema_cfg_folder = constants.get_schema_config_location(tk.project_path)   
    config = FolderConfiguration(tk, schema_cfg_folder)
    
    # create an object to receive all IO requests
    io_receiver = FolderIOReceiver(tk, preview)

    # now loop over all individual objects and create folders
    for entity_type, entity_ids in items.items():
        for entity_id in entity_ids:
            create_single_folder_item(tk, config, io_receiver, entity_type, entity_id, engine)

    tk.execute_hook(constants.POST_PROCESS_FOLDER_CREATION_HOOK_NAME,
                    processed_items=io_receiver.get_creation_history(), 
                    preview=preview)

    return io_receiver.get_computed_items()
