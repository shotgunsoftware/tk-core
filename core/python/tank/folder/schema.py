"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Methods and classes for generating folders based on the high level schema scaffold.

Known constraints:
 - won't allow the same entity type to appear more than once in the path. (ie Asset > Sub Asset)

"""

import os
import fnmatch

from .folder import Static, ListField, Entity, Project, Token, UserWorkspace

from .. import root
from ..path_cache import PathCache
from ..errors import TankError
from ..platform import constants

from tank_vendor import yaml


class Schema(object):
    """
    Represents the entire schema file and is the main entry point for the folder creation.
    """
    
    def __init__(self, tk, schema_config_path, create_folder, copy_file, preview):
        """
        Constructor
        
        :param sg: shotgun API handle
        :param project_root: project root folder on disk
        :param schema_config_path: path to the schema configuration root folder
        :param create_folder: create folder callback
        :param copy_file: copy file callback
        :param preview: preview mode
        """
        
        self.sg = tk.shotgun
        self.tk = tk
        self.project_root = tk.project_path
        self.projects = []
        self.num_entity_folders = 0
        self._nodes_by_name = None

        # keep track of stuff we are creating
        self.created_items = list()
        
        # check if we are using the preview mode
        self._preview_mode = preview
        self._make_folder_callback = create_folder
        self._copy_file_callback = copy_file

        self._path_cache = PathCache(self.project_root)

        # read skip files config
        self.ignore_files = _read_ignore_files(schema_config_path)

        # TODO: Check path exists and is a project.        
        self._load_schema(schema_config_path)
    
    def create_folders(self, entity_type, entity_id, engine=None):
        """
        Creates folders for an entity type and an entity id.
                
        :param entity_type: Shotgun entity type
        :param entity_id: Shotgun entity id
        :param engine: Engine to create folders for / indicate second pass if not None.
        
        :returns: how many sg entity folders were processed
        """
        # TODO: Confirm this entity exists and is in this project
        
        # reset folder counter
        self.num_entity_folders = 0
        
        # Recurse over entire tree and find find all Entity folders of this type
        if entity_type == "Project":
            # handle project as a special case. we know them all already...
            folders = self.projects
        else:
            # recurse from each project folder to look for folders of the desired type
            folders = []
            for project in self.projects:
                folders.extend(project.find_entity_folders(entity_type))
        
        # For each folder, find the list of entities needed to build the full path and
        # ensure its parent folders exist. Then, create the folder for this entity with
        # all its children.
        for folder in folders:
            parents = []
            
            # fill in the information we know about this entity now
            tokens = { 
                entity_type: { "type": entity_type, "id": entity_id }
            }
            
            # now go up the tree and populate parents and tokens
            self._visit(folder, tokens, parents)
            
            # get the parent folder of the project
            if entity_type == "Project":
                path = os.path.abspath(os.path.join(folder.root_path, os.path.pardir))
            else:
                path = os.path.abspath(os.path.join(parents[-1].root_path, os.path.pardir))
            
            # now walk down from the project level until we reach our entity 
            # and create all the structure, then create our entity's children.
            to_visit = [folder] + parents
            to_visit.pop().create_folders(self, path, tokens, to_visit, engine=engine)
            
        # return how many folders were created
        return self.num_entity_folders
    
        
    def add_entry_to_cache_db(self, path, entity_type, entity_id, entity_name):
        """
        Adds entity to database. 
        """
        if not self._preview_mode:            
            existing_paths = self._path_cache.get_paths(entity_type, entity_id)
            if path not in existing_paths:
                # path not in cache yet - add it now!
                self._path_cache.add_mapping(entity_type, entity_id, entity_name, path)
        
    def make_folder(self, path, entity):
        """
        Calls make folder callback.
        """
        self.created_items.append(path)
        if not self._preview_mode:
            self._make_folder_callback(path, entity)            
    
    def copy_file(self, src_path, target_path):
        """
        Calls copy file callback.
        """
        self.created_items.append(target_path)
        if not self._preview_mode:
            self._copy_file_callback(src_path, target_path)            

    def _visit(self, folder, tokens, parents):
        if isinstance(folder, Entity):
            folder.extract_tokens(self.sg, tokens)
        
        if folder.parent:
            parents.append(folder.parent)
            self._visit(folder.parent, tokens, parents)
    
    ##########################################################################################
    # loading scaffold from disk
    
    def _resolve_reference(self, ref_token, node_path):
        """
        Resolves a $ref_token to an object by going up the tree
        until it finds a match.
        """
        curr_path = node_path
        while True:
            # look at parent folder
            curr_path = os.path.abspath(os.path.join(curr_path, ".."))

            # look it up in the nodes dict
            obj = self._nodes_by_name.get(curr_path)
            # abort if not found
            if obj is None:
                raise TankError("Could not find token %s starting from %s" % (ref_token, node_path))

            # skip static folders (project folder in single root project is special case.)
            # check if there is a yml file with the same name
            yml_file = "%s.yml" % curr_path
            if os.path.basename(curr_path) == "project"   or os.path.exists(yml_file):
                # the curr folder name matches the $reference! It's a match! 
                if os.path.basename(curr_path) == ref_token:
                    return obj
    
    
    def _create_static_node(self, full_path, parent_node, metadata):
        """
        Create a user static object from a metadata file
        """
        file_name = os.path.basename(full_path)
        defer_creation = metadata.get("defer_creation", False)
        return Static(parent_node, file_name, defer_creation)        

    
    def _create_user_workspace_node(self, full_path, parent_node, metadata):
        """
        Create a user workspace object from a metadata file
        """
        sg_name_expression = metadata.get("name")
        defer_creation = metadata.get("defer_creation", True)
        
        # validate
        if sg_name_expression is None:
            raise TankError("Missing name token in yml metadata file %s" % full_path )

        return UserWorkspace(parent_node, sg_name_expression, defer_creation, self.sg)


    def _create_sg_entity_node(self, full_path, parent_node, metadata):
        """
        Create an entity object from a metadata file
        """
        # get data
        sg_name_expression = metadata.get("name")
        entity_type = metadata.get("entity_type")
        filters = metadata.get("filters")
        create_with_parent = metadata.get("create_with_parent", False)
        defer_creation = metadata.get("defer_creation", False)
        
        # validate
        if sg_name_expression is None:
            raise TankError("Missing name token in yml metadata file %s" % full_path )
        
        if entity_type is None:
            raise TankError("Missing entity_type token in yml metadata file %s" % full_path )

        if filters is None:
            raise TankError("Missing filters token in yml metadata file %s" % full_path )

        # transform
        #
        # example:
        # filters: [ { "path": "project", "relation": "is", "values": [ "$project" ] } ]
        
        # in order to find $Project, traverse the file system upwards, looking for
        # a path that has a folder named "project".
        
        for sg_filter in filters:
            values = sg_filter["values"]
            new_values = []
            for filter_value in values:
                if filter_value.startswith("$"):
                    #process
                    referenced_node = self._resolve_reference(filter_value[1:], full_path)
                    
                    if isinstance(referenced_node, Entity):
                        # append a token to the filter with the entity TYPE of the sg node
                        new_values.append( Token(referenced_node.entity_type) )
                    elif isinstance(referenced_node, ListField):
                        # append a token to the filter of the form Asset.sg_asset_type
                        new_values.append( Token(referenced_node.entity_type + "." + referenced_node.field_name) )
                    else:
                        raise TankError("Folder creation metadata file for %s "
                                        "has a filter %s which refers to an " 
                                        "unknown node %s!" % (full_path, sg_filter, filter_value))
                else:
                    new_values.append(filter_value)
            sg_filter["values"] = new_values
        
        # make a filters that the entity object expects
        entity_filter = {}
        entity_filter["logical_operator"] = "and"
        entity_filter["conditions"] = filters
        
        # construct
        return Entity(parent_node, entity_type, sg_name_expression, entity_filter, create_with_parent, defer_creation)
    
    def _create_sg_list_field_node(self, full_path, parent_node, metadata):
        """
        Create a list field object from a metadata file
        """
        # get data
        entity_type = metadata.get("entity_type")
        field_name = metadata.get("field_name")
        skip_unused = metadata.get("skip_unused", False)
        defer_creation = metadata.get("defer_creation", False)
        
        # validate
        if entity_type is None:
            raise TankError("Missing entity_type token in yml metadata file %s" % full_path )
        
        if field_name is None:
            raise TankError("Missing field_name token in yml metadata file %s" % full_path )
        
        # construct
        return ListField(parent_node, entity_type, field_name, skip_unused, defer_creation)
    
    
    
    
    def _process_config_r(self, parent_node, parent_path):
        """
        Recursively scan the file system and construct an object
        hierarchy
        """
        for full_path in self._directory_paths(parent_path):
            # check for metadata (non-static folder)
            metadata = self._read_metadata(full_path)
            if metadata:
                node_type = metadata.get("type", "undefined")
                
                if node_type == "shotgun_entity":
                    cur_node = self._create_sg_entity_node(full_path, parent_node, metadata)
                    
                elif node_type == "shotgun_list_field":
                    cur_node = self._create_sg_list_field_node(full_path, parent_node, metadata)
                    
                elif node_type == "static":
                    cur_node = self._create_static_node(full_path, parent_node, metadata)
                
                elif node_type == "user_workspace":
                    cur_node = self._create_user_workspace_node(full_path, parent_node, metadata)
                
                else:
                    # don't know this metadata
                    raise TankError("Unknown metadata type '%s'" % node_type)
            else:
                # no metadata - so this is just a static folder!
                cur_node = self._create_static_node(full_path, parent_node, {})

            self._nodes_by_name[full_path] = cur_node
            # and process children
            self._process_config_r(cur_node, full_path)
           
        # now process all files and add them to the parent_node token
        for f in self._file_paths(parent_path):
            parent_node.add_file(f)
    
    def _directory_paths(self, parent_path):
        directory_paths = []
        for file_name in os.listdir(parent_path):
            full_path = os.path.join(parent_path, file_name)
            # ignore files
            if os.path.isdir(full_path) and not file_name.startswith("."):
                directory_paths.append(full_path)
        return directory_paths

    def _file_paths(self, parent_path):
        file_paths = []
        for file_name in os.listdir(parent_path):

            # don't process files matching ignore pattern(s)
            if not any(fnmatch.fnmatch(file_name, p) for p in self.ignore_files):

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
                metadata = yaml.load(open_file)
                open_file.close()
            except Exception, error:
                raise TankError("Cannot load config file '%s'. Error: %s" % (yml_file, error))
        return metadata
    
    def _load_schema(self, schema_config_path):
        """
        Scan the config and build objects structure
        """
        
        # maintain a dictionary of nodes by name
        self._nodes_by_name = {} 
        
        project_dirs = self._directory_paths(schema_config_path)
        
        if len(project_dirs) == 1:
            # Only one project root
            project_root = os.path.join(schema_config_path, "project")
            
            if not os.path.exists(project_root):
                raise TankError("Could not find a root folder named 'project' in %s!" % schema_config_path)
             
            # make root node
            project = Project(self.project_root)
            self.projects.append(project)
            self._nodes_by_name[project_root] = project
             
            # recursively process the rest
            self._process_config_r(project, project_root)
        elif len(project_dirs) > 1:
            # Multiple project roots
            roots = root.get_project_roots(self.project_root)
            for project_dir in project_dirs:
                project_root = os.path.join(schema_config_path, project_dir)
                
                # read metadata to determine root path 
                metadata = self._read_metadata(project_root)
                if metadata:
                    if metadata.get("type", None) != "project":
                        raise TankError("Only directories of type 'project' are allowed at the schema root. %s" % project_root)
                    root_name = metadata.get("root_name", None)
                    if root_name is None:
                        raise TankError("Missing or invalid value for 'root_name' in metadata for project directory %s" % project_root)

                    root_path = roots.get(root_name, None)
                    if root_path is None:
                        raise TankError("No path is specified for root %s" % root_name)
                else:
                    raise TankError("Project directory missing required metadata file: %s" % project_root)
                
                project = Project(root_path)
                self.projects.append(project)
                self._nodes_by_name[project_root] = project
                self._process_config_r(project, project_root)
        else:
            raise TankError("Could not find a project root folder in %s!" % schema_config_path)

def _read_ignore_files(schema_config_path):
    """
    Reads ignore_files from root of schema if it exists.
    """
    ignore_files = []
    file_path = os.path.join(schema_config_path, "ignore_files")
    if os.path.exists(file_path):
        open_file = open(file_path, "r")
        for line in open_file.readlines():
            # skip comments
            if "#" in line:
                line = line[:line.index("#")]
            line = line.strip()
            if line:
                ignore_files.append(line)
        open_file.close()
    return ignore_files


################################################################################################
# public functions
    
def process_filesystem_structure(tk, entity_type, entity_ids, preview, engine=None):    
    """
    Creates filesystem structure in Tank based on Shotgun and a schema config.
    Internal version.
    
    :param tk: A tank instance
    :param entity_type: A shotgun entity type to create folders for
    :param entity_ids: list of entity ids to process
    :param preview: enable dry run mode?
    :param engine: (Optional) A string representation matching a level in the schema. Passing this
                   option indicates to the system that a second pass should be executed and all
                   which are marked as deferred are processed.
    
    :returns: tuple: (How many entity folders were processed, list of items)
    
    """


    # Ensure ids is a list
    if not isinstance(entity_ids, (list, tuple)):
        if isinstance(entity_ids, int):
            entity_ids = (entity_ids,)
        elif isinstance(entity_ids, str) and entity_ids.isdigit():
            entity_ids = (int(entity_ids),)
        else:
            raise ValueError("Parameter entity_ids was passed %s, accepted types are list, typle and int.")

    
    if len(entity_ids) == 0:
        return

    # all things to create, organized by type
    items = {}

    # Add the project
    # assume all entites belong to the same project
    if entity_type != "Project":
        data = tk.shotgun.find_one(entity_type, [["id", "is", entity_ids[0]]], ["project"])
        if not data:
            raise TankError("Unable to find entity in shotgun. type: %s, id: %s" % (entity_type, entity_ids[0]))
        project_id = data["project"]["id"]
        items["Project"] = [project_id]

    # if entity_type is a task, get the entity connected to the task
    # a selection of tasks may be connected to multiple shotgun entity types
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



    # Define a create folder callback.
    def _make_folder_callback(path, entity):
        # pass on request to hook
        tk.execute_hook(constants.CREATE_FOLDERS_CORE_HOOK_NAME, path=path, sg_entity=entity)
        
    # Define a copy file callback.
    def _copy_file_callback(source_path, target_path):
        # pass on request to hook
        tk.execute_hook(constants.COPY_FILE_CORE_HOOK_NAME, 
                        source_path=source_path, 
                        target_path=target_path)

    # get some constants
    schema_cfg_folder = constants.get_schema_config_location(tk.project_path)   

    # create schema builder
    schema = Schema(tk, 
                    schema_cfg_folder, 
                    _make_folder_callback, 
                    _copy_file_callback, 
                    preview)
        
    entities_processed = 0
    for entity_type, entity_ids in items.items():
        for entity_id in entity_ids:
            entities_processed += schema.create_folders(entity_type, entity_id, engine)

    return (entities_processed, schema.created_items)
