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
Folder Classes representing various types of dynamic behaviour 
"""
import os
import copy

from ..util import shotgun_entity
from ..util import login
from ..errors import TankError


class Folder(object):
    """
    Abstract Base class for all other folder classes.
    """
    
    def __init__(self, parent, full_path, config_metadata):
        """
        Constructor
        """
        self._config_metadata = config_metadata
        self._children = []
        self._full_path = full_path
        self._parent = parent
        self._files = []
        self._symlinks = []
        
        if self._parent:
            # add me to parent's child list
            self._parent._children.append(self)
            
        
    def __repr__(self):
        class_name = self.__class__.__name__
        return "<%s %s>" % (class_name, self._full_path)
            
    ###############################################################################################
    # public methods
    
    def is_dynamic(self):
        """
        Returns true if this folder node requires some sort of dynamic input
        """
        # assume all nodes are dynamic unless explicitly stated
        return True
    
    def get_path(self):
        """
        Returns the path on disk to this configuration item
        """
        return self._full_path
            
    def get_parent(self):
        """
        Returns the folder parent, none if no parent was defined
        """
        return self._parent
        
    def extract_shotgun_data_upwards(self, sg, shotgun_data):
        """
        Extract data from shotgun for a specific pathway upwards through the
        schema. 
        
        This is subclassed by deriving classes which process Shotgun data.
        For more information, see the Entity implementation.
        """
        if self._parent is None:
            return shotgun_data
        else:
            return self._parent.extract_shotgun_data_upwards(sg, shotgun_data)
            
    def get_parents(self):
        """
        Returns all parent nodes as a list with the top most item last in the list
        
        e.g. [ </foo/bar/baz>, </foo/bar>, </foo> ]
        """
        if self._parent is None:
            return []
        else:
            return [self._parent] + self._parent.get_parents()
            
    def add_file(self, path):
        """
        Adds a file name that should be added to this folder as part of processing.
        The file path should be absolute.
        """
        self._files.append(path)
        
    def add_symlink(self, name, target, metadata):
        """
        Adds a symlink definition to this node. As part of the processing phase, symlink
        targets will be resolved and created.
        
        :param name: name of the symlink
        :param target: symlink target expression
        :param metadata: full config yml metadata for symlink
        """
        # first split the target expression into chunks
        resolved_expression = [ SymlinkToken(x) for x in target.split("/") ]
        self._symlinks.append({"name": name, "target": resolved_expression, "metadata": metadata })
        
    def create_folders(self, io_receiver, path, sg_data, is_primary, explicit_child_list, engine):
        """
        Recursive folder creation. Creates folders for this node and all its children.
        
        :param io_receiver: An object which handles any io processing request. Note that
                            processing may be deferred and happen after the recursion has completed.
               
        :param path: The file system path to the location where this folder should be 
                     created.
                     
        :param sg_data: All Shotgun data, organized in a dictionary, as returned by 
                        extract_shotgun_data_upwards()
                     
        :param is_primary: Indicates that the folder is part of the primary creation chain
                           and not part of the secondary recursion. For example, if the 
                           folder creation is running for shot ABC, the primary chain
                           folders would be Project X -> Sequence Y -> Shot ABC.
                           The secondary folders would be the children of Shot ABC.
                          
        :param explicit_child_list: A list of specific folders to process as the algorithm
                                    traverses down. Each time a new level is traversed, the child
                                    list is popped, and that object is processed. If the 
                                    child list is empty, all children will be processed rather
                                    than the explicit object given at each level.
                                    
                                    This effectively means that folder creation often starts off
                                    using an explicit child list (for example project->sequence->shot)
                                    and then when the child list has been emptied (at the shot level),
                                    the recursion will switch to a creation mode where all Folder 
                                    object children are processed. 
                                  
        :param engine: String used to limit folder creation. If engine is not None, folder creation
                       traversal will include nodes that have their deferred flag set.
        
        :returns: Nothing
        """
        
        # should we create any folders?
        if not self._should_item_be_processed(engine, is_primary):
            return
        
        # run the actual folder creation
        created_data = self._create_folders_impl(io_receiver, path, sg_data)
        
        # and recurse down to children
        if explicit_child_list:
            
            # we have been given a specific list to recurse down.
            # pop off the next item and process it.
            explicit_ch = copy.copy(explicit_child_list)
            child_to_process = explicit_ch.pop()
            
            # before recursing down our specific recursion path, make sure all static content
            # has been created at this level in the folder structure
            static_children = [ch for ch in self._children if ch.is_dynamic() == False]
            
            for (created_folder, sg_data_dict) in created_data:

                # first process the static folders                
                for cp in static_children:
                    # note! if the static child is on the specific recursion path,
                    # skip it, (we will create it below)
                    if cp == child_to_process:
                        continue
                    
                    cp.create_folders(io_receiver, 
                                      created_folder, 
                                      sg_data_dict, 
                                      is_primary=False, 
                                      explicit_child_list=[], 
                                      engine=engine)
                
                # and then recurse down our specific recursion path
                child_to_process.create_folders(io_receiver, 
                                                created_folder, 
                                                sg_data_dict, 
                                                is_primary=True, 
                                                explicit_child_list=explicit_ch, 
                                                engine=engine)
                 
            
            
        else:
            # no explicit list! instead process all children.            
            # run the folder creation for all new folders created and for all
            # configuration children
            for (created_folder, sg_data_dict) in created_data:
                for cp in self._children:
                    cp.create_folders(io_receiver, 
                                      created_folder, 
                                      sg_data_dict, 
                                      is_primary=False, 
                                      explicit_child_list=[], 
                                      engine=engine)
            

    ###############################################################################################
    # private/protected methods

    def _create_folders_impl(self, io_receiver, parent_path, sg_data):
        """
        Folder creation implementation. Implemented by all subclasses.
        
        Should return a list of tuples. Each tuple is a path + a matching shotgun data dictionary
        """
        raise NotImplementedError
    
    def _should_item_be_processed(self, engine_str, is_primary):
        """
        Checks if this node should be processed, given its deferred status.
        
        If deriving classes have other logic for deciding if a node should be processsed,
        this method can be sublcassed. However, the base class should also be executed.
        
        Is Primary indicates that the folder is part of the primary creation pass.
        
        in the metadata, expect the following values:
        
        --                                    # no config parameter at all, means always create
        defer_creation:                       # no value specified, means create folders
        defer_creation: false                 # create folders
        defer_creation: true                  # create for all engine_str <> None
        defer_creation: tk-maya               # create if engine_str matches
        defer_creation: [tk-maya, tk-nuke]    # create if engine_str is in list
        """
        

        dc_value = self._config_metadata.get("defer_creation")
        # if defer_creation config param not specified or None means we 
        # can always go ahead with folder creation!!
        if dc_value is None or dc_value == False:
            # deferred value not specified means proceed with creation!
            return True

        # now handle the cases where the config specifies some sort of deferred behaviour
        # first of all, if the passed engine_str is None, we know we are NOT in deferred mode,
        # so shouldn't proceed.        
        if engine_str is None:
            return False
            
        # now handle all cases where we have an engine_str and some sort of deferred behaviour.
        if dc_value == True:
            # defer create for all engine_strs!
            return True
        
        if isinstance(dc_value, basestring) and dc_value == engine_str:
            # defer_creation parameter is a string and this matches the engine_str!
            return True
        
        if isinstance(dc_value, list) and engine_str in dc_value:
            # defer_creation parameter is a list and the engine_str is contained in this list
            return True
        
        # for all other cases, no match!
        return False
        

    def _process_symlinks(self, io_receiver, path, sg_data):
        """
        Helper method.
        Resolves all symlinks and requests creation via the io_receiver object.
        
        :param io_receiver: IO handler instance
        :param path: Path where the symlinks should be located
        :param sg_data: std shotgun data collection for the current object
        """ 
        
        for symlink in self._symlinks:
            
            full_path = os.path.join(path, symlink["name"])                        
            
            # resolve our symlink from the target expressions 
            # this will resolve any $project, $shot etc.
            # we get a list of strings representing resolved values for all levels of the symlink
            resolved_target_chunks = [ x.resolve_token(self, sg_data) for x in symlink["target"] ]

            # and join them up into a path string
            resolved_target_path = os.path.sep.join(resolved_target_chunks)
            
            # register symlink with the IO receiver 
            io_receiver.create_symlink(full_path, resolved_target_path, symlink["metadata"])
        

    def _copy_files_to_folder(self, io_receiver, path):
        """
        Helper.
        Copies all files that have been registered with this folder object
        to a specific target folder on disk, using the dedicated hook.
        
        :param io_receiver: IO handler instance
        :param path: Path where the symlinks should be located
        """
        for src_file in self._files:
            target_path = os.path.join(path, os.path.basename(src_file))
            io_receiver.copy_file(src_file, target_path, self._config_metadata)

################################################################################################

class Static(Folder):
    """
    Represents a static folder in the file system
    """
    
    @classmethod
    def create(cls, tk, parent, full_path, metadata):
        """
        Factory method for this class
        """
        
        # get data
        constrain_by_entity = metadata.get("constrain_by_entity")
        constraints = metadata.get("constraints")
        
        create_with_parent = metadata.get("create_with_parent", True)
        
        # validate
        if constrain_by_entity is not None and constraints is None:
            raise TankError("Missing constraints parameter in yml metadata file %s" % full_path )
        
        if constraints is not None and constrain_by_entity is None:
            raise TankError("Configuration error in %s: Need to have a "
                            "constrain_by_entity token in order "
                            "for the constraints parameter to be picked up." % full_path )

        # resolve dynamic constraints filter ($shot, $step etc).
        if constraints:
            constraints_filter = _translate_filter_tokens(constraints, parent, full_path)
            
            # resolve the constrained_by_entity ($shot, $step etc) 
            resolved_constrain_node = None
            curr_parent = parent
            while curr_parent:
                full_folder_path = curr_parent.get_path()
                folder_name = os.path.basename(full_folder_path)
                if folder_name == constrain_by_entity[1:]:
                    resolved_constrain_node = curr_parent
                    break
                else:
                    curr_parent = curr_parent.get_parent()
            
            if resolved_constrain_node is None:
                raise TankError("Configuration error in %s: constrain_by_entity '%s' could not "
                            "be resolved into a parent node. It needs to be on the form '$name', "
                            "where name is the name of a parent yaml "
                            "configuration file."  % (full_path, constrain_by_entity))

        
            if not isinstance(resolved_constrain_node, Entity):
                raise TankError("Configuration error in %s: constrain_by_entity points "
                                "at a node which is not associated with any Shotgun data. " 
                                "You can only constrain based on nodes which have a Shotgun "
                                "representation." % full_path )
                   
        else:
            # no constraints active for this static node
            resolved_constrain_node = None
            constraints_filter = None
                        
        return Static(parent, 
                      full_path, 
                      metadata, 
                      tk, 
                      create_with_parent, 
                      resolved_constrain_node, 
                      constraints_filter)
    
    def __init__(self, parent, full_path, metadata, tk, create_with_parent, constrain_node, constraints_filter):
        """
        Constructor.
        """
        Folder.__init__(self, parent, full_path, metadata)
        
        # The name parameter represents the folder name that will be created in the file system.
        self._name = os.path.basename(full_path)
        
        self._constrain_node = constrain_node
        self._constraints_filter = constraints_filter 
        self._create_with_parent = create_with_parent 
        self._tk = tk
        
        self._cached_sg_data = {}
    
    def is_dynamic(self):
        """
        Returns true if this folder node requires some sort of dynamic input
        """
        return False
    
    def _should_item_be_processed(self, engine_str, is_primary):
        """
        Checks if this node should be processed, given its deferred status.        
        """
        # check our special condition - is this node set to be auto-created with its parent node?
        # note that primary nodes are always created with their parent nodes!
        if is_primary == False and self._create_with_parent == False:
            return False
        
        # base class implementation
        return super(Static, self)._should_item_be_processed(engine_str, is_primary)
    
    
    def _create_folders_impl(self, io_receiver, parent_path, sg_data):
        """
        Creates a static folder.
        """
        
        # first check if we have any conditionals that need evaluating
        if self._constrain_node:
            
            # resolve our sg filter expression based on the current shotgun data
            # for the current parent objects (for example if the query expression
            # contains $shot or other dynamic tokens)
            resolved_filters = _resolve_shotgun_filters(self._constraints_filter, sg_data)
            
            # so now resolved_filters is something like:
            # {'logical_operator': 'and', 
            #  'conditions': [{'path': 'code', 'values': ['a'], 'relation': 'contains'}] }
            # 
            # and the configuration states that the constraint object is $shot
            # which is resolved into self._constrain_node
            #
            # now we want to get the current parent $shot id. This can be extrated
            # from the sg_data dict which is on the form:
            # {'Project': {'id': 88, 'type': 'Project'},
            # 'Sequence': {'id': 32, 'type': 'Sequence'},
            # 'Shot': {'id': 1184, 'type': 'Shot'},
            # 'Step': {'id': 5, 'type': 'Step'}}
            # 
            # once extracted, we can add that to the sg filter to get our final filter:
            # 
            # {'logical_operator': 'and', 
            #  'conditions': [{'path': 'code', 'values': ['a'], 'relation': 'contains'},
            #                 {'path': 'id', 'values': [1184], 'relation': 'is'} ] }
            
            constrain_entity_id = sg_data[ self._constrain_node.get_entity_type() ]["id"]
            id_filter = {'path': 'id', 'values': [constrain_entity_id], 'relation': 'is'}
            resolved_filters["conditions"].append(id_filter)
            
            # depending on the filter, it is possible that the same static query will 
            # be generated more than once - so cache the results so that we can minimize
            # shotgun queries.
            hash_key = hash(str(resolved_filters))
            
            if hash_key in self._cached_sg_data:
                data = self._cached_sg_data[hash_key]
            
            else:
                # call out to shotgun
                data = self._tk.shotgun.find_one(self._constrain_node.get_entity_type(), resolved_filters)
                # and cache it
                self._cached_sg_data[hash_key] = data
                        
            if data is None:
                # no match! this means that our constraints filter did not match the current object
                return []
        
        # create our folder
        my_path = os.path.join(parent_path, self._name)
        
        # call out to callback
        io_receiver.make_folder(my_path, self._config_metadata)

        # copy files across
        self._copy_files_to_folder(io_receiver, my_path)

        # process symlinks
        self._process_symlinks(io_receiver, my_path, sg_data)

        return [ (my_path, sg_data) ]

################################################################################################

class ListField(Folder):
    """
    Represents values from a Shotgun list field in the file system (like Asset.sg_asset_type)
    """
    
    @classmethod
    def create(cls, tk, parent, full_path, metadata):
        """
        Factory method for this class
        """
        # read configuration
        entity_type = metadata.get("entity_type")
        field_name = metadata.get("field_name")
        skip_unused = metadata.get("skip_unused", False)
        create_with_parent = metadata.get("create_with_parent", False)
        
        # validate
        if entity_type is None:
            raise TankError("Missing entity_type token in yml metadata file %s" % full_path )
        
        if field_name is None:
            raise TankError("Missing field_name token in yml metadata file %s" % full_path )
        
        return ListField(tk, parent, full_path, metadata, entity_type, field_name, skip_unused, create_with_parent)

    def __init__(self, tk, parent, full_path, metadata, entity_type, field_expr, skip_unused, create_with_parent):
        """
        Constructor
        """

        Folder.__init__(self, parent, full_path, metadata)
        
        self._tk = tk
        self._entity_type = entity_type
        self._create_with_parent = create_with_parent 
        self._field_expr_obj = shotgun_entity.EntityExpression(self._tk, self._entity_type, field_expr)
        self._skip_unused = skip_unused    
        
        # now ensure that the expression only contains a single field
        if len(self._field_expr_obj.get_shotgun_fields()) != 1:
            raise TankError("Configuration error in %s: Field expression '%s' must contain "
                            "exactly one field!" % (full_path, field_expr))
        
        # get the single shotgun field that the expression is based on
        sg_fields = self._field_expr_obj.get_shotgun_fields()
        # get the first element of the returned set
        self._field_name = list(sg_fields)[0]
        
    def _should_item_be_processed(self, engine_str, is_primary):
        """
        Checks if this node should be processed, given its deferred status.        
        """
        # list fields are only created when they are on the primary path,
        # e.g. we don't recurse down to create asset types when shots are created,
        # but only when assets are created.
        if is_primary == False and self._create_with_parent == False:
            return False
        
        # base class implementation
        return super(ListField, self)._should_item_be_processed(engine_str, is_primary)
        
        
    def get_entity_type(self):
        """
        Returns the entity type associated with this node
        """
        return self._entity_type
        
    def get_field_name(self):
        """
        Returns the field name associated with this list field
        """
        return self._field_name
        
    def _create_folders_impl(self, io_receiver, parent_path, sg_data):
        """
        Creates a list field folder. 
        """
        
        # first see if this item has already been declared inside the sg_data structure
        # this would happen if for example the same structure was defined twice:
        # /project/asset_type/asset/asset_type/work
        # it also happens when we recurse upwards to preload the sg_data dict
        # from an entity.
        # 
        token_name = FilterExpressionToken.sg_data_key_for_folder_obj(self)
                
        if token_name in sg_data:
            values = [ sg_data[token_name] ]
                
        else:
            
            # get all list field values from shotgun by querying the schema methods
            # using schema_field_read()
            #
            # example response:
            #
            # {'sg_asset_type': {'data_type': {'editable': False, 'value': 'list'},
            #                    'description': {'editable': True, 'value': ''},
            #                    'editable': {'editable': False, 'value': True},
            #                    'entity_type': {'editable': False, 'value': 'Asset'},
            #                    'mandatory': {'editable': False, 'value': False},
            #                    'name': {'editable': True, 'value': 'Type'},
            #                    'properties': {'default_value': {'editable': False,
            #                                                     'value': None},
            #                                   'summary_default': {'editable': True,
            #                                                       'value': 'none'},
            #                                   'valid_values': {'editable': True,
            #                                                    'value': ['Character',
            #                                                              'Vehicle',
            #                                                              'Prop',
            #                                                              'Environment',
            #                                                              'Matte Painting']}}}}
            #

            
            if "." in self._field_name:
                # this looks like a deep link - entity.EntityType.fieldname
                # unfold the expression before getting the values
                try:
                    chunks = self._field_name.split(".")
                    entity_type = chunks[1]
                    field_name = chunks[2]
                except:
                    msg = "Folder creation error: Cannot resolve the field expression %s." % self._field_name
                    raise TankError(msg)
            
            else:
                # field name is a non-deep-link field (e.g 'sg_asset_type')
                entity_type = self._entity_type
                field_name = self._field_name
                
            try:
                resp = self._tk.shotgun.schema_field_read(entity_type, field_name)
            
                # validate that the data type is of type list
                field_type = resp[field_name]["data_type"]["value"]
            except Exception, e:
                msg = "Folder creation error: Cannot retrieve values for Shotgun list field "
                msg += "%s.%s. Error reported: %s" % (entity_type, field_name, e)
                raise TankError(msg)
                
            if field_type != "list":
                msg = "Folder creation error: Only list fields can be used with the list field type. "
                msg += "%s.%s is of type %s which is unsupported." % (entity_type, field_name, field_type)
                raise TankError(msg)
            
            # get all values
            values = resp[field_name]["properties"]["valid_values"]["value"]
                
            if self._skip_unused:
                # cull values based on their usage - EXPENSIVE WITH ONE SG QUERY PER VALUE
                values = self.__filter_unused_list_values(entity_type, 
                                                          field_name, 
                                                          values, 
                                                          sg_data.get("Project"))
        
        # process each value independently
        products = []
                        
        for sg_value in values:
            
            # render field expression 
            folder_name = self._field_expr_obj.generate_name({self._field_name: sg_value})
            
            # construct folder
            my_path = os.path.join(parent_path, folder_name)
            io_receiver.make_folder(my_path, self._config_metadata)
            
            # copy files across
            self._copy_files_to_folder(io_receiver, my_path)
            
            # create a new tokens dict including our own data. This will be used
            # by the main folder recursion when processing the child folder objects.
            new_sg_data = copy.deepcopy(sg_data)
            new_sg_data[token_name] = sg_value 

            # process symlinks
            self._process_symlinks(io_receiver, my_path, new_sg_data)
            
            products.append( (my_path, new_sg_data) )
            
        return products
        
    def __filter_unused_list_values(self, entity_type, field_name, values, project):
        """
        Remove values which are not used by entities in this project.
        
        - WARNING! SLOW! Will do a shotgun query for every value in values.
        - WARNING! This logic will check if a value is 'unused' by looking at all items
                   for that entity type. This may be perfectly fine (in the case of asset type
                   and asset for example, however it will not be relevant if other filter criteria
                   are also applied at the same time (e.g. if we are for example only processing 
                   tasks of type Foo then we would ideally want to query the unused-ness based on 
                   this subset, not based on all tasks in the project.
        """
        used_values = []

        for value in values:
            
            # eg. sg_asset_type is prop
            filters = [ [field_name, "is", value] ] 
            if project:
                filters.append( ["project", "is", project] )
    
            summary = self._tk.shotgun.summarize(entity_type, 
                                                 filters, 
                                                 [{"field": field_name, "type": "count"}])
            if summary.get("summaries", {}).get(field_name):
                used_values.append(value)

        return used_values

################################################################################################

class SymlinkToken(object):
    """
    Represents a folder level in a symlink target.
    """
    
    def __init__(self, name):
        self._name = name
    
    def __repr__(self):
        return "<SymlinkToken token '%s'>" % self._name
    
    def resolve_token(self, folder_obj, sg_data):
        """
        Returns a resolved value for this token.
        """
        if self._name.startswith("$"):
            
            # strip the dollar sign
            token = self._name[1:]
            
            # check that the referenced token is matching one of the tokens which 
            # has a computed name part to represent the dynamically created folder name
            # this computed_name field exists for all entity folders for example.
            valid_tokens = [x for x in sg_data if (isinstance(sg_data[x], dict) and sg_data[x].has_key("computed_name"))]
            
            if token not in valid_tokens:
                raise TankError("Cannot compute symlink target for %s: The reference token '%s' cannot be resolved. "
                                "Available tokens are %s." % (folder_obj, self._name, valid_tokens)) 
            
            name_value = sg_data[token].get("computed_name")
            
            return name_value
            
        else:
            # not an expression
            return self._name



class CurrentStepExpressionToken(object):
    """
    Represents the current step
    """
    
    def __init__(self, sg_task_step_link_field):
        self._sg_task_step_link_field = sg_task_step_link_field
    
    def __repr__(self):
        return "<CurrentStepId token. Task link field: %s>" % self._sg_task_step_link_field
    
    def resolve_shotgun_data(self, shotgun_data):
        """
        Given a shotgun data dictionary, return an appropriate value 
        for this expression. 
        
        Because the entire design is centered around "normal" entities, 
        the task data is preloaded prior to calling the folder recursion.
        If there is a notion of a current task, this data is contained
        in a current_task_data dictionary which contains information about 
        the current task and its connections (for example to a pipeline step).
        """
        
        sg_task_data = shotgun_data.get("current_task_data")
        
        if sg_task_data:
            # we have information about the currently processed task
            # now see if there is a link field to a step
            
            if self._sg_task_step_link_field in sg_task_data:
                # this is a link field linking the task to its associated step
                # (a step does not necessarily need to be a pipeline step)
                # now get the id for this target entity. 
                sg_task_shot_link_data = sg_task_data[self._sg_task_step_link_field]
                
                if sg_task_shot_link_data:
                    # there is a link from task -> step present
                    return sg_task_shot_link_data["id"]
        
        # if data is missing, return None to indicate this.
        return None
    

class CurrentTaskExpressionToken(object):
    """
    Represents the current task
    """
    
    def __init__(self):
        pass
    
    def __repr__(self):
        return "<CurrentTaskId token>"
    
    def resolve_shotgun_data(self, shotgun_data):
        """
        Given a shotgun data dictionary, return an appropriate value 
        for this expression.
        
        Because the entire design is centered around "normal" entities, 
        the task data is preloaded prior to calling the folder recursion.
        If there is a notion of a current task, this data is contained
        in a current_task_data dictionary which contains information about 
        the current task and its connections (for example to a pipeline step).
        """
        sg_task_data = shotgun_data.get("current_task_data")
        
        if sg_task_data:            
            return sg_task_data.get("id")
        else:
            return None


class FilterExpressionToken(object):
    """
    Represents a $token in a filter expression for entity nodes.
    """
    
    @classmethod
    def sg_data_key_for_folder_obj(cls, folder_obj):
        """
        Returns the data key to be used with a particular folder object
        For list nodes this is EntityType.fieldname
        For sg nodes this is EntityType
        
        This data key is used in the data dictionary that is preloaded
        and passed around the folder resolve methods.
        """
        if isinstance(folder_obj, Entity):
            # append a token to the filter with the entity TYPE of the sg node
            sg_data_key = folder_obj.get_entity_type()
            
        elif isinstance(folder_obj, ListField):
            # append a token to the filter of the form Asset.sg_asset_type
            sg_data_key = "%s.%s" % (folder_obj.get_entity_type(), folder_obj.get_field_name())
            
        elif isinstance(folder_obj, Static):
            # Static folders cannot be used with folder $expressions. This error
            # is typically caused by a missing .yml file
            raise TankError("Static folder objects (%s) cannot be used in dynamic folder "
                            "expressions using the \"$\" syntax. Perhaps you are missing "
                            "the %s.yml file in your schema?" % (folder_obj, os.path.basename(folder_obj._full_path)))
            
        else:
            raise TankError("The folder object %s cannot be used in folder $expressions" % folder_obj)
        
        return sg_data_key
    
    def __init__(self, expression, parent):
        """
        Constructor
        """
        self._expression = expression
        if self._expression.startswith("$"):
            self._expression = self._expression[1:]
        
        # now find which node is being pointed at
        referenced_node = self._resolve_ref_r(parent)
        
        if referenced_node is None:
            raise TankError("The configuration expression $%s could not be found in %s or in "
                            "any of its parents." % (self._expression, parent))

        self._sg_data_key = self.sg_data_key_for_folder_obj(referenced_node)
        
        # all the nodes we refer to have a concept of an entity type.
        # store that too so that for later use
        self._associated_entity_type = referenced_node.get_entity_type() 
        
    def __repr__(self):
        return "<FilterExpression '%s' >" % self._expression

    def _resolve_ref_r(self, folder_obj):
        """
        Resolves a $ref_token to an object by going up the tree
        until it finds a match. The token is compared against the 
        folder name of the configuration item.
        """
        full_folder_path = folder_obj.get_path()
        folder_name = os.path.basename(full_folder_path)
        
        if folder_name == self._expression:
            # match!
            return folder_obj
        
        parent = folder_obj.get_parent()
        if parent is None:
            return parent # end recursion!
        
        # try parent 
        return self._resolve_ref_r(parent)
        
    def get_entity_type(self):
        """
        Returns the shotgun entity type for this link
        """
        return self._associated_entity_type
        
        
    def resolve_shotgun_data(self, shotgun_data):
        """
        Given a shotgun data dictionary, return an appropriate value 
        for this expression.
        """
        if self._sg_data_key not in shotgun_data:
            raise TankError("Cannot resolve data key %s from "
                            "shotgun data bundle %s" % (self._sg_data_key, shotgun_data))
        
        value = shotgun_data[self._sg_data_key]
        return value

    def get_sg_data_key(self):
        """
        Returns the data key that is associated with this expression.
        When passing around pre-fetched shotgun data for node population,
        this is done as a dictionary. The sg data key indicates which 
        part of this dictionary is associated with a particular $reference token. 
        """
        return self._sg_data_key



class EntityLinkTypeMismatch(Exception):
    """
    Exception raised to indicate that a shotgun 
    entity link is incorrectly typed
    and therefore cannot be traversed.
    
    For example, imagine there is an entity Workspace which 
    can link to both shots and assets via an sg_entity link.
    
    you then have two configuration branches:
    
    project->asset->workspace
       \-->shot->workspace
    
    you now have a workspace entity with id 123 which links to an asset.
    
    If you run extract_shotgun_data_upwards method for id 123
    and start from the folder object in the shot branch, the link
    will be mismatching since the sg_entity for id 123 points at an 
    asset not a shot. In those cases, this exception is being raised
    from inside  extract_shotgun_data_upwards.
    """
    


class Entity(Folder):
    """
    Represents an entity in Shotgun
    """
    
    @classmethod
    def create(cls, tk, parent, full_path, metadata):
        """
        Factory method for this class
        """
        
        # get data
        sg_name_expression = metadata.get("name")
        entity_type = metadata.get("entity_type")
        filters = metadata.get("filters")
        create_with_parent = metadata.get("create_with_parent", False)
        
        # validate
        if sg_name_expression is None:
            raise TankError("Missing name token in yml metadata file %s" % full_path )
        
        if entity_type is None:
            raise TankError("Missing entity_type token in yml metadata file %s" % full_path )

        if filters is None:
            raise TankError("Missing filters token in yml metadata file %s" % full_path )
        
        entity_filter = _translate_filter_tokens(filters, parent, full_path)
                
        return Entity(tk, parent, full_path, metadata, entity_type, sg_name_expression, entity_filter, create_with_parent)
    
    
    def __init__(self, tk, parent, full_path, metadata, entity_type, field_name_expression, filters, create_with_parent):
        """
        Constructor.
        
        The filter syntax for deciding which folders to create
        is a dictionary, often looking something like this:
        
             {
                 "logical_operator": "and",
                 "conditions": [ { "path": "project", "relation": "is", "values": [ FilterExpressionToken(<Project>) ] } ]
             }
        
        This is basically a shotgun API filter dictionary, but with interleaved tokens 
        (e.g. the FilterExpressionToken object). Tank will resolve any Token fields prior to 
        passing the filter to Shotgun for evaluation.
        """
        
        # the schema name is the same as the SG entity type
        Folder.__init__(self, parent, full_path, metadata)
        
        self._tk = tk
        self._entity_type = entity_type
        self._entity_expression = shotgun_entity.EntityExpression(self._tk, self._entity_type, field_name_expression)
        self._filters = filters
        self._create_with_parent = create_with_parent    
    
    def __get_name_field_for_et(self, entity_type):
        """
        return the special name field for a given entity
        """
        spec_name_fields = {"Project": "name", "Task": "content", "HumanUser": "name"}
        if entity_type in spec_name_fields:
            return spec_name_fields[entity_type]
        else:
            return "code"

    
    def get_entity_type(self):
        """
        returns the shotgun entity type for this node
        """
        return self._entity_type
    
    def _should_item_be_processed(self, engine_str, is_primary):
        """
        Checks if this node should be processed, given its deferred status.        
        """
        # check our special condition - is this node set to be auto-created with its parent node?
        # note that primary nodes are always created with their parent nodes!
        if is_primary == False and self._create_with_parent == False:
            return False
        
        # base class implementation
        return super(Entity, self)._should_item_be_processed(engine_str, is_primary)
    
    def _create_folders_impl(self, io_receiver, parent_path, sg_data):
        """
        Creates folders.
        """
        items_created = []
        
        for entity in self.__get_entities(sg_data):

            # generate the field name            
            folder_name = self._entity_expression.generate_name(entity)
            
            # now for the case where the project name is encoded with slashes,
            # we need to translate those into a native representation
            folder_name = folder_name.replace("/", os.path.sep)
            
            my_path = os.path.join(parent_path, folder_name)
                        
            # get the name field - which depends on the entity type
            # Note: this is the 'name' that will get stored in the path cache for this entity
            name_field = self.__get_name_field_for_et(self._entity_type)
            name_value = entity[name_field]            
            # construct a full entity link dict w name, id, type
            full_entity_dict = {"type": self._entity_type, "id": entity["id"], "name": name_value} 
                        
            # register secondary entity links
            self._register_secondary_entities(io_receiver, my_path, entity)
                        
            # call out to callback
            io_receiver.make_entity_folder(my_path, full_entity_dict, self._config_metadata)

            # copy files across
            self._copy_files_to_folder(io_receiver, my_path)

            # create a new entity dict including our own data and pass it down to children
            my_sg_data = copy.deepcopy(sg_data)
            my_sg_data_key = FilterExpressionToken.sg_data_key_for_folder_obj(self)
            my_sg_data[my_sg_data_key] = { "type": self._entity_type, "id": entity["id"], "computed_name": folder_name }

            # process symlinks
            self._process_symlinks(io_receiver, my_path, my_sg_data)
            
            items_created.append( (my_path, my_sg_data) )
            
        return items_created
    

    def _register_secondary_entities(self, io_receiver, path, entity):
        """
        Looks in the entity dict for any linked entities and register these 
        """
        # get all the link fields from the name expression
        for lf in self._entity_expression.get_shotgun_link_fields():
            
            entity_link = entity[lf]
            io_receiver.register_secondary_entity(path, entity_link, self._config_metadata)

    def __get_entities(self, sg_data):
        """
        Returns shotgun data for folder creation
        """
        # first check the constraints: if tokens contains a type/id pair our our type,
        # we should only process this single entity. If not, then use the query filter
        
        # first, resolve the filter queries for the current ids passed in via tokens
        resolved_filters = _resolve_shotgun_filters(self._filters, sg_data)
        
        # see if the sg_data dictionary has a "seed" entity type matching our entity type
        my_sg_data_key = FilterExpressionToken.sg_data_key_for_folder_obj(self)
        if my_sg_data_key in sg_data:
            # we have a constraint!
            entity_id = sg_data[my_sg_data_key]["id"]
            # add the id constraint to the filters
            resolved_filters["conditions"].append({ "path": "id", "relation": "is", "values": [entity_id] })
            # get data - can be None depending on external filters

        # figure out which fields to retrieve
        fields = self._entity_expression.get_shotgun_fields()
        
        # add any shotgun link fields used in the expression
        fields.update( self._entity_expression.get_shotgun_link_fields() )
        
        # always retrieve the name field for the entity
        fields.add( self.__get_name_field_for_et(self._entity_type) )        
        
        # convert to a list - sets wont work with the SG API
        fields_list = list(fields)
        
        # now find all the items (e.g. shots) matching this query
        entities = self._tk.shotgun.find(self._entity_type, resolved_filters, fields_list)
        
        return entities

    def extract_shotgun_data_upwards(self, sg, shotgun_data):
        """
        Extracts the shotgun data necessary to create this object and all its parents.
        The shotgun_data input needs to contain a dictionary with a "seed". For example:
        { "Shot": {"type": "Shot", "id": 1234 } }
        
        
        This method will then first extend this structure to ensure that fields needed for
        folder creation are available:
        { "Shot": {"type": "Shot", "id": 1234, "code": "foo", "sg_status": "ip" } }
        
        Now, if you have structure with Project > Sequence > Shot, the Shot level needs
        to define a configuration entry roughly on the form 
        filters: [ { "path": "sg_sequence", "relation": "is", "values": [ "$sequence" ] } ]
        
        So in addition to getting the fields required for naming the current entry, we also
        get all the fields that are represented by $tokens. These will form the 'seed' for
        when we recurse to the parent level and do the same thing there.
        
        
        The return data is on the form:
        {
            'Project':   {'id': 4, 'name': 'Demo Project', 'type': 'Project'},
            'Sequence':  {'code': 'Sequence1', 'id': 2, 'name': 'Sequence1', 'type': 'Sequence'},
            'Shot':      {'code': 'shot_010', 'id': 2, 'type': 'Shot'}
        }        
        
        NOTE! Because we are using a dictionary where we key by type, it would not be possible
        to have a pathway where the same entity type exists multiple times. For example an 
        asset / sub asset relationship.
        """
        
        tokens = copy.deepcopy(shotgun_data)
        
        # If we don't have an entry in tokens for the current entity type, then we can't
        # extract any tokens. Used by #17726. Typically, we start with a "seed", and then go
        # upwards. For example, if the seed is a Shot id, we then scan upwards, look at the config
        # for shot, which contains [sg_sequence is $sequence], e.g. the shot entry links explicitly
        # to the sequence entry. Because of this link, by the time we move upwards in the hierarchy
        # and reach sequence, we will already have an entry for sequence in the dictionary.
        # 
        # however, if we have a free-floating item in the hierarchy, this will not be 'seeded' 
        # by its children as we move upwards - for example a step.
        my_sg_data_key = FilterExpressionToken.sg_data_key_for_folder_obj(self)
        if my_sg_data_key in tokens:

            
            link_map = {}
            fields_to_retrieve = []
            additional_filters = []
            
            # TODO: Support nested conditions
            for condition in self._filters["conditions"]:
                vals = condition["values"]
                
                # note the $FROM$ condition below - this is a bit of a hack to make sure we exclude
                # the special $FROM$ step based culling filter that is commonly used. Because steps are 
                # sort of free floating and not associated with an entity, removing them from the 
                # resolve should be fine in most cases.
                
                # so - if at the shot level, we have defined the following filter:
                # filters: [ { "path": "sg_sequence", "relation": "is", "values": [ "$sequence" ] } ]
                # the $sequence will be represented by a Token object and we need to get a value for 
                # this token. We fetch the id for this token and then, as we recurse upwards, and process
                # the parent folder level (the sequence), this id will be the "seed" when we populate that
                # level. 
                
                if vals[0] and isinstance(vals[0], FilterExpressionToken) and not condition["path"].startswith('$FROM$'):
                    expr_token = vals[0]
                    # we should get this field (eg. 'sg_sequence')
                    fields_to_retrieve.append(condition["path"])
                    # add to our map for later processing map['sg_sequence'] = 'Sequence'
                    # note that for List fields, the key is EntityType.field
                    link_map[ condition["path"] ] = expr_token 
                
                elif not condition["path"].startswith('$FROM$'):
                    # this is a normal filter (we exclude the $FROM$ stuff since it is weird
                    # and specific to steps.) So for example 'name must begin with X' - we want 
                    # to include these in the query where we are looking for the object, to
                    # ensure that assets with names starting with X are not created for an 
                    # asset folder node which explicitly excludes these via its filters. 
                    additional_filters.append(condition)
            
            # add some extra fields apart from the stuff in the config
            if self._entity_type == "Project":
                fields_to_retrieve.append("name")
            elif self._entity_type == "Task":
                fields_to_retrieve.append("content")
            elif self._entity_type == "HumanUser":
                fields_to_retrieve.append("login")
            else:
                fields_to_retrieve.append("code")
            
            # TODO: AND the id query with this folder's query to make sure this path is
            # valid for the current entity. Throw error if not so driver code knows to 
            # stop processing. This would be needed in a setup where (for example) Asset
            # appears in several locations in the filesystem and that the filters are responsible
            # for determining which location to use for a particular asset.
            my_id = tokens[ my_sg_data_key ]["id"]
            additional_filters.append( {"path": "id", "relation": "is", "values": [my_id]})
            
            # append additional filter cruft
            filter_dict = { "logical_operator": "and", "conditions": additional_filters }
            
            # carry out find
            rec = sg.find_one(self._entity_type, filter_dict, fields_to_retrieve)
            
            # there are now two reasons why find_one did not return:
            # - the specified entity id does not exist or has been deleted
            # - there are filters which has filtered it out. For example imagine that you 
            #   have one folder structure for all assets starting with A and a second structure
            #   for the rest. This would be a filter condition (code does not start with A, and
            #   code starts with A respectively). In these cases, the object does exist but has been
            #   explicitly filtered out - which is not an error!
            
            if not rec:
                
                # check if it is a missing id or just a filtered out thing
                if sg.find_one(self._entity_type, [["id", "is", my_id]]) is None:                
                    raise TankError("Could not find Shotgun %s with id %s as required by "
                                    "the folder creation setup." % (self._entity_type, my_id))
                else:
                    raise EntityLinkTypeMismatch()
            
            # and append the 'name field' which is always needed.
            name = None # used for error reporting
            if self._entity_type == "Project":
                name = rec["name"]
                tokens[ my_sg_data_key ]["name"] = rec["name"]
            elif self._entity_type == "Task":
                name = rec["content"]
                tokens[ my_sg_data_key ]["content"] = rec["content"]
            elif self._entity_type == "HumanUser":
                name = rec["login"]
                tokens[ my_sg_data_key ]["login"] = rec["login"]
            else:
                name = rec["code"]
                tokens[ my_sg_data_key ]["code"] = rec["code"]
            
            
            # Step through our token key map and process
            #
            # This is on the form
            # link_map['sg_sequence'] = link_obj
            #
            for field in link_map:
                
                # do some juggling to make sure we don't double process the 
                # name fields.
                value = rec[field]
                link_obj = link_map[field]
                
                if value is None:
                    # field was none! - cannot handle that!
                    raise TankError("The %s %s has a required field %s that \ndoes not have a value "
                                    "set in Shotgun. \nDouble check the values and try "
                                    "again!\n" % (self._entity_type, name, field))
    
                if isinstance(value, dict):
                    # If the value is a dict, assume it comes from a entity link.
                    
                    # now make sure that this link is actually relevant for us,
                    # e.g. that it points to an entity of the right type.
                    # this may be a problem whenever a link can link to more
                    # than one type. See the EntityLinkTypeMismatch docs for example.
                    if value["type"] != link_obj.get_entity_type():
                        raise EntityLinkTypeMismatch()
                    
                
                # store it in our sg_data prefetch chunk
                tokens[ link_obj.get_sg_data_key() ] = value
                
        # now keep recursing upwards
        if self._parent is None:
            return tokens
        
        else:
            return self._parent.extract_shotgun_data_upwards(sg, tokens)
    
    
class UserWorkspace(Entity):
    """
    Represents a user workspace folder. 
    
    A workspace folder is deferred by default and is typically created in a second pass, just before
    application startup.
    """
    
    @classmethod
    def create(cls, tk, parent, full_path, metadata):
        """
        Factory method for this class
        """
        # get config
        sg_name_expression = metadata.get("name")
        filters = metadata.get("filters", [])
        entity_filter = _translate_filter_tokens(filters, parent, full_path)
        
        # validate
        if sg_name_expression is None:
            raise TankError("Missing name token in yml metadata file %s" % full_path )

        
        return UserWorkspace(tk, parent, full_path, metadata, sg_name_expression, entity_filter)
    
    
    def __init__(self, tk, parent, full_path, metadata, field_name_expression, entity_filter):
        """
        constructor
        """
        
        # lazy setup: we defer the lookup of the current user until the folder node
        # is actually being utilized, see extract_shotgun_data_upwards() below
        self._user_initialized = False
        
        # user work spaces are always deferred so make sure to add a setting to the metadata
        # note: This should ideally be a parameter passed to the base class.
        metadata["defer_creation"] = True
        
        Entity.__init__(self, 
                        tk,
                        parent, 
                        full_path,
                        metadata,
                        "HumanUser", 
                        field_name_expression, 
                        entity_filter, 
                        create_with_parent=True)
        
    def create_folders(self, io_receiver, path, sg_data, is_primary, explicit_child_list, engine):
        """
        Inherited and wrapps base class implementation
        """
        
        # wraps around the Entity.create_folders() method and adds
        # the current user to the filer query in case this has not already been done.
        # having this set up before the first call to create_folders rather than in the
        # constructor is partly for performance, but primarily so that a valid current user 
        # isn't required unless you actually create a user sandbox folder. For example,
        # if you have a dedicated machine that creates higher level folders, this machine
        # shouldn't need to have a user id set up - only the artists that actually create 
        # the user folders should need to.
        
        if not self._user_initialized:

            # this query confirms that there is a matching HumanUser in shotgun for the local login
            user = login.get_current_user(self._tk) 
    
            if not user:
                msg = ("Folder Creation Error: Could not find a HumanUser in shotgun with login " 
                       "matching the local login. Check that the local login corresponds to a "
                       "user in shotgun.")
                raise TankError(msg)
    
            user_filter = { "path": "id", "relation": "is", "values": [ user["id"] ] }
            self._filters["conditions"].append( user_filter )            
            self._user_initialized = True
        
        return Entity.create_folders(self, io_receiver, path, sg_data, is_primary, explicit_child_list, engine)
        


class ShotgunStep(Entity):
    """
    Represents a Shotgun Pipeline Step
    """
    
    @classmethod
    def create(cls, tk, parent, full_path, metadata):
        """
        Factory method for this class
        """
        # get config
        sg_name_expression = metadata.get("name")
        if sg_name_expression is None:
            raise TankError("Missing name token in yml metadata file %s" % full_path )

        create_with_parent = metadata.get("create_with_parent", True)
        
        entity_type = metadata.get("entity_type", "Step")
        task_link_field = metadata.get("task_link_field", "step")
        associated_entity_type = metadata.get("associated_entity_type")
        
        filters = metadata.get("filters", [])
        entity_filter = _translate_filter_tokens(filters, parent, full_path)
        
        return ShotgunStep(tk, 
                           parent, 
                           full_path, 
                           metadata, 
                           sg_name_expression, 
                           create_with_parent, 
                           entity_filter,
                           entity_type,
                           task_link_field,
                           associated_entity_type)
    
    
    def __init__(self, 
                 tk, 
                 parent, 
                 full_path, 
                 metadata, 
                 field_name_expression, 
                 create_with_parent, 
                 entity_filter, 
                 entity_type, 
                 task_link_field,
                 associated_entity_type):
        """
        constructor
        """
        
        self._entity_type = entity_type
        self._task_link_field = task_link_field
        
        # look up the tree for the first parent of type Entity which is not a User
        # this is because the user is typically assigned to a sandbox
        # and no-one would have steps actually associated with a user anyways 
        # (seems like a highly unlikely case anyone would ever do that)
        # so skip over user in order to support folder configs where
        # you have for example Asset -> User Sandbox -> (Asset) Step
        # refer to this in our query expression.
        #
        # It is also possible to set the associated_entity_type parameter
        # if you want to specifically tie this step to a particular level.
        # This is useful if you are setting up for example
        # Asset > CUSTOM > Step - custom being workspace, application etc.
        # and you want the step to associate.
        #
        sg_parent = parent
        while True:
                        
            if associated_entity_type is None and \
               isinstance(sg_parent, Entity) and \
               sg_parent.get_entity_type() != "HumanUser":
                # there is no specific entity type set so
                # grab the first entity we'll find except user workspaces             
                break
            
            elif associated_entity_type is not None and \
                 isinstance(sg_parent, Entity) and \
                 sg_parent.get_entity_type() == associated_entity_type:
                # we have found the specific parent that the step is associated with
                break
            
            elif sg_parent is None:
                raise TankError("Error in configuration %s - node must be parented "
                                "under a shotgun entity." % full_path)
            
            else:
                sg_parent = sg_parent.get_parent()
            
        # get the parent name for the entity expression, e.g. $shot
        parent_name = os.path.basename(sg_parent.get_path())
        
        # create a token object to represent the parent link
        parent_expr_token = FilterExpressionToken(parent_name, sg_parent)

        # now create the shotgun filter query for this note that the query 
        # uses this weird special syntax to restrict the pipeline steps 
        # created only to be ones actually used with the entity
        
        # The syntax here is $FROM$Task.CONNECTION_FIELD.entity, where the connection field
        # is "step" by default
        step_filter_path = "$FROM$Task.%s.entity" % self.get_task_link_field() 
        
        step_filter = {"path": step_filter_path, "relation": "is", "values": [parent_expr_token] }
        entity_filter["conditions"].append( step_filter )
        
        # if the create_with_parent setting is True, it means that if we create folders for a 
        # shot, we want all the steps to be created at the same time.
        # however, if we have create_with_parent set to False, we only want to create 
        # this node if we are creating folders for a task.
        if create_with_parent != True: 
            # do not auto-create with parent - only create when a task has been specified.
            # create an expression object to represent the current step.
            # we pass in the field which is the connection between the task and the step field
            current_step_id_token = CurrentStepExpressionToken( self.get_task_link_field() )
            # add this to the filters so that we restrict the filter to be 
            # step id is 1234 (where 1234 is the current step derived from the current task
            # and the current task comes from the original folder create request).
            entity_filter["conditions"].append({"path": "id", "relation": "is", "values": [current_step_id_token]})

        Entity.__init__(self, 
                        tk,
                        parent, 
                        full_path,
                        metadata,
                        self.get_step_entity_type(), 
                        field_name_expression, 
                        entity_filter, 
                        create_with_parent=True)
                
        
    def get_task_link_field(self):       
        """
        Each step node is associated with a task via special link field on task.
        This method returns the name of that link field as a string
        """
        return self._task_link_field
    
    def get_step_entity_type(self):
        """
        Returns the Shotgun entity type which is used to represent the pipeline step.
        Shotgun has a built in pipeline step which is a way of grouping tasks together
        into distinct sets, however it is sometimes useful to be able to use a different
        entity to perform this grouping.
        """
        return self._entity_type


class ShotgunTask(Entity):
    """
    Represents a Shotgun Task
    """
    
    @classmethod
    def create(cls, tk, parent, full_path, metadata):
        """
        Factory method for this class
        """
        # get config
        sg_name_expression = metadata.get("name")
        if sg_name_expression is None:
            raise TankError("Missing name token in yml metadata file %s" % full_path )

        create_with_parent = metadata.get("create_with_parent", False)
        
        associated_entity_type = metadata.get("associated_entity_type")
        
        filters = metadata.get("filters", [])
        entity_filter = _translate_filter_tokens(filters, parent, full_path)
        
        return ShotgunTask(tk, 
                           parent, 
                           full_path, 
                           metadata, 
                           sg_name_expression, 
                           create_with_parent, 
                           entity_filter, 
                           associated_entity_type)
    
    
    def __init__(self, 
                 tk, 
                 parent, 
                 full_path, 
                 metadata, 
                 field_name_expression, 
                 create_with_parent, 
                 entity_filter,
                 associated_entity_type):
        """
        constructor
        """
        
        # look up the tree for the first parent of type Entity
        # refer to this in our query expression
        
        # look up the tree for the first parent of type Entity which is not a User
        # this is because the user is typically assigned to a sandbox
        # and no-one would have tasks actually associated with a user anyways 
        # (seems like a highly unlikely case anyone would ever do that)
        # so skip over user in order to support folder configs where
        # you have for example Asset -> User Sandbox -> (Asset) Task
        # refer to this in our query expression.
        #
        # It is also possible to set the associated_entity_type parameter
        # if you want to specifically tie this task to a particular level.
        # This is useful if you are setting up for example
        # Asset > CUSTOM > Task - custom being workspace, application etc.
        # and you want the step to associate.
        #
        sg_parent_entity = None
        sg_parent_step = None
        curr_parent = parent
        
        while True:
        
            if associated_entity_type is None and \
               isinstance(curr_parent, Entity) and \
               not isinstance(curr_parent, ShotgunStep) and \
               curr_parent.get_entity_type() != "HumanUser":
                # found an entity! Job done!
                sg_parent_entity = curr_parent
                break

            elif isinstance(curr_parent, ShotgunStep):
                sg_parent_step = curr_parent            
        
            elif curr_parent is None:
                raise TankError("Error in configuration %s - node must be parented "
                                "under a shotgun entity." % full_path)
            
            elif associated_entity_type is not None and \
                 isinstance(curr_parent, Entity) and \
                 curr_parent.get_entity_type() == associated_entity_type:
                # we have found the specific parent that the step is associated with
                sg_parent_entity = curr_parent
                break
                        
            curr_parent = curr_parent.get_parent()
        
        # get the parent name for the entity expression, e.g. $shot
        # create a token object to represent the parent link
        parent_entity_name = os.path.basename(sg_parent_entity.get_path())
        parent_entity_expr_token = FilterExpressionToken(parent_entity_name, sg_parent_entity)
        
        # now create the base shotgun filter query for this
        task_filter = {"path": "entity", "relation": "is", "values": [parent_entity_expr_token] }
        entity_filter["conditions"].append( task_filter )
                
        # check if there is a step filter defined above this task node in the hierarchy
        if sg_parent_step:
            # this task has a step above it in the hierarchy
            # make sure we include that in the filter
            parent_step_name = os.path.basename(sg_parent_step.get_path())
            parent_step_expr_token = FilterExpressionToken(parent_step_name, sg_parent_step)
            entity_filter["conditions"].append({"path": sg_parent_step.get_task_link_field(), 
                                                "relation": "is", 
                                                "values": [parent_step_expr_token]})
        
        # if the create_with_parent setting is True, it means that if we create folders for a 
        # shot, we want all the tasks to be created at the same time.
        # however, if we have create_with_client set to False, we only want to create 
        # this node if we are creating folders for a task.
        if create_with_parent != True: 
            # do not auto-create with parent - only create when a task has been specified.
            # create an expression object to represent the current step
            current_task_id_token = CurrentTaskExpressionToken()
            # add this to the filters so that we restrict the filter to be 
            # step id is 1234 (where 1234 is the current step derived from the current task
            # and the current task comes from the original folder create request).
            entity_filter["conditions"].append({"path": "id", "relation": "is", "values": [current_task_id_token]})
        
        Entity.__init__(self, 
                        tk,
                        parent, 
                        full_path,
                        metadata,
                        "Task", 
                        field_name_expression, 
                        entity_filter, 
                        create_with_parent=True)
                
        
        





class Project(Entity):
    """
    The root point. Represents a shotgun project.
    """
    
    @classmethod
    def create(cls, tk, schema_config_project_folder, metadata):
        """
        Factory method for this class
        """
        
        storage_name = metadata.get("root_name", None)
        if storage_name is None:
            raise TankError("Missing or invalid value for 'root_name' in metadata: %s" % schema_config_project_folder)
        
        
        # now resolve the disk location for the storage specified in the project config
        local_roots = tk.pipeline_configuration.get_local_storage_roots()
        
        if storage_name not in local_roots:
            raise TankError("The storage '%s' specified in the folder configuration %s.yml does not exist "
                            "in the storage configuration!" % (storage_name, schema_config_project_folder))
        
        storage_root_path = local_roots[storage_name]

        return Project(tk, schema_config_project_folder, metadata, storage_root_path)
    
    
    def __init__(self, tk, schema_config_project_folder, metadata, storage_root_path):
        """
        constructor
        """
                
        no_filters = {
            "logical_operator": "and",
            "conditions": []
        }
        
        self._tk = tk
        self._storage_root_path = storage_root_path
        
        Entity.__init__(self, 
                        tk,
                        None, 
                        schema_config_project_folder,
                        metadata,
                        "Project", 
                        "tank_name", 
                        no_filters, 
                        create_with_parent=False)
                
    def get_storage_root(self):
        """
        Local storages are defined in the Shotgun preferences.
        This method returns the local OS path that is associated with the
        local storage that this project node is associated with.
        (By default, this is the primary storage, but if you have a multi
        root config, there may be more than one project node.)        
        """
        return self._storage_root_path
        

def _resolve_shotgun_filters(filters, sg_data):
    """
    Replace Token instances in the filters with a real value from the tokens dictionary.

    This method processes the filters dictionary and replaces tokens with data found
    in the tokens dictionary. It returns a resolved filter dictionary that can be passed to 
    a shotgun query.
    """
    # TODO: Support nested conditions
    resolved_filters = copy.deepcopy(filters)
    for condition in resolved_filters["conditions"]:
        vals = condition["values"]
        
        if vals[0] and isinstance(vals[0], FilterExpressionToken):
            # we got a $filter! - replace with resolved value
            expr_token = vals[0]
            vals[0] = expr_token.resolve_shotgun_data(sg_data)
        
        if vals[0] and isinstance(vals[0], CurrentStepExpressionToken):
            # we got a current step filter! - replace with resolved value
            expr_token = vals[0]
            vals[0] = expr_token.resolve_shotgun_data(sg_data)

        if vals[0] and isinstance(vals[0], CurrentTaskExpressionToken):
            # we got a current task filter! - replace with resolved value
            expr_token = vals[0]
            vals[0] = expr_token.resolve_shotgun_data(sg_data)                

    return resolved_filters


def _translate_filter_tokens(filter_list, parent, yml_path):
    """
    Helper method to translate dynamic filter tokens into FilterExpressionTokens.
    
    For example - the following filter list:
    [ { "path": "project", "relation": "is", "values": [ "$project" ] } ]
    
    Will be translated to:
    
    { "logical_operator": "and",
      "conditions": [ { "path": "project", 
                        "relation": "is", 
                        "values": [ FilterExpressionTokens(project) ] } 
                    ] }
    """
    
    resolved_filters = copy.deepcopy(filter_list)
    
    for sg_filter in resolved_filters:
        values = sg_filter["values"]
        new_values = []
        for filter_value in values:
            if isinstance(filter_value, basestring) and filter_value.startswith("$"):
                # this is a filter expression!
                try:
                    expr_token = FilterExpressionToken(filter_value, parent)
                except TankError, e:
                    # specialized message
                    raise TankError("Error resolving filter expression "
                                    "%s in %s.yml: %s" % (filter_list, yml_path, e))
                new_values.append(expr_token)
            else:
                new_values.append(filter_value)
                
        sg_filter["values"] = new_values
    
    # add the wrapper around the list to make shotgun happy 
    entity_filter = {}
    entity_filter["logical_operator"] = "and"
    entity_filter["conditions"] = resolved_filters
    
    return entity_filter
    
