"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

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
        
        
        if self._parent:
            # add me to parent's child list
            self._parent._children.append(self)
            
        
    def __repr__(self):
        class_name = self.__class__.__name__
        return "<%s %s>" % (class_name, self._full_path)
            
    ###############################################################################################
    # public methods
            
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
                
    def create_folders(self, io_receiver, path, sg_data, explicit_child_list, engine):
        """
        Recursive folder creation. Creates folders for this node and all its children.
        
        :param io_receiver: An object which handles any io processing request. Note that
                            processing may be deferred and happen after the recursion has completed.
               
        :param path: The file system path to the location where this folder should be 
                     created.
                     
        :param sg_data: All Shotgun data, organized in a dictionary, as returned by 
                        extract_shotgun_data_upwards()
                          
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
        # if the explicit child list exists, this take precedence - we always want to create
        # those children.
        if not explicit_child_list:
            if not self._should_item_be_processed(engine):
                return
        
        # run the actual folder creation
        created_data = self._create_folders_impl(io_receiver, path, sg_data)
        
        # and recurse down to children
        if explicit_child_list:
            # we have been given a specific list to recurse down.
            # pop off the next item and process it.
            explicit_ch = copy.deepcopy(explicit_child_list)
            ch = explicit_ch.pop()
            children_to_process = [ch]
            
        else:
            # no explicit list! instead process all children.
            explicit_ch = []
            children_to_process = self._children
            
        # run the folder creation for all new folders created and for all
        # configuration children
        for (created_folder, sg_data_dict) in created_data:
            for cp in children_to_process:
                cp.create_folders(io_receiver, created_folder, sg_data_dict, explicit_ch, engine)
            

    ###############################################################################################
    # private/protected methods

    def _create_folders_impl(self, io_receiver, parent_path, sg_data):
        """
        Folder creation implementation. Implemented by all subclasses.
        
        Should return a list of tuples. Each tuple is a path + a matching shotgun data dictionary
        """
        raise NotImplementedError
    
    def _should_item_be_processed(self, engine_str):
        """
        Checks if this node should be processed, given its deferred status.
        
        If deriving classes have other logic for deciding if a node should be processsed,
        this method can be sublcassed. However, the base class should also be executed.
        
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
        

    def _copy_files_to_folder(self, io_receiver, path):
        """
        Helper.
        Copies all files that have been registered with this folder object
        to a specific target folder on disk, using the dedicated hook
        """
        for src_file in self._files:
            target_path = os.path.join(path, os.path.basename(src_file))
            io_receiver.copy_file(src_file, target_path)

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
        return Static(parent, full_path, metadata)
    
    def __init__(self, parent, full_path, metadata):
        """
        Constructor.
        """
        Folder.__init__(self, parent, full_path, metadata)
        
        # The name parameter represents the folder name that will be created in the file system.
        self._name = os.path.basename(full_path)
    
    def _create_folders_impl(self, io_receiver, parent_path, sg_data):
        """
        Creates a static folder.
        """
        # create our folder
        my_path = os.path.join(parent_path, self._name)
        
        # call out to callback
        io_receiver.make_folder(my_path)

        # copy files across
        self._copy_files_to_folder(io_receiver, my_path)

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
        skip_unused = metadata.get("skip_unused")
        if skip_unused is None:
            skip_unused = False
        
        # validate
        if entity_type is None:
            raise TankError("Missing entity_type token in yml metadata file %s" % full_path )
        
        if field_name is None:
            raise TankError("Missing field_name token in yml metadata file %s" % full_path )
        
        return ListField(tk, parent, full_path, metadata, entity_type, field_name, skip_unused)

    def __init__(self, tk, parent, full_path, metadata, entity_type, field_expr, skip_unused):
        """
        Constructor
        """

        Folder.__init__(self, parent, full_path, metadata)
        
        self._tk = tk
        self._entity_type = entity_type
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
        Creates a static folder. Returns the created folder.
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
            # get all fields from the schema in shotgun via the API
            # (the SG API raises appropriate exceptions on failure so no need to catch) 
            resp = self._tk.shotgun.schema_field_read(self._entity_type, self._field_name)
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
            
            # validate that the data type is of type list
            field_type = resp[self._field_name]["sg_asset_type"]["data_type"]["value"]
            if field_type != "list":
                msg = "Folder creation error: Only list fields can be used with the list field type. "
                msg += "%s.%s is of type %s which is unsupported." % (self._entity_type, self._field_name, field_type)
                raise TankError(msg)
            
            # get all values
            values = resp[self._field_name]["properties"]["valid_values"]["value"]
                
            if self._skip_unused:
                # cull values based on their usage
                values = self.__filter_unused_list_values(values, sg_data.get("Project"))
        
        # process each value independently
        products = []
                        
        for sg_value in values:
            
            # render field expression 
            folder_name = self._field_expr_obj.generate_name({self._field_name: sg_value})
            
            # construct folder
            my_path = os.path.join(parent_path, folder_name)
            io_receiver.make_folder(my_path)
            
            # copy files across
            self._copy_files_to_folder(io_receiver, my_path)
            
            # create a new tokens dict including our own data. This will be used
            # by the main folder recursion when processing the child folder objects.
            new_sg_data = copy.deepcopy(sg_data)
            new_sg_data[token_name] = sg_value
            
            products.append( (my_path, new_sg_data) )
            
        return products
        
    def __filter_unused_list_values(self, values, project):
        """
        Remove values which are not used by entities in this project.
        Will do a shotgun query for every value in values.
        """
        used_values = []

        for value in values:
            
            # eg. sg_asset_type is prop
            filters = [ [self._field_name, "is", value] ] 
            if project:
                filters.append( ["project", "is", project] )
    
            summary = self._tk.shotgun.summarize(self._entity_type, filters, [{'field':self._field_name, 'type': 'count'}])
            if summary.get("summaries", {}).get(self._field_name):
                used_values.append(value)

        return used_values

################################################################################################

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
        self._referenced_node = self._resolve_ref_r(parent)
        
        if self._referenced_node is None:
            raise TankError("The configuration expression $%s could not be found in %s or in "
                            "any of its parents." % (self._expression, parent))

        self._sg_data_key = self.sg_data_key_for_folder_obj(self._referenced_node)
        

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
        return self._referenced_node.get_entity_type()
        
        
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
        
        
        # transform filter expressions into FilterExpressionTokens
        # example:
        # filters: [ { "path": "project", "relation": "is", "values": [ "$project" ] } ]
        for sg_filter in filters:
            values = sg_filter["values"]
            new_values = []
            for filter_value in values:
                if filter_value.startswith("$"):
                    # create object
                    try:
                        expr_token = FilterExpressionToken(filter_value, parent)
                    except TankError, e:
                        # specialized message
                        raise TankError("Error resolving filter expression "
                                        "%s for %s: %s" % (filters, full_path, e))
                    new_values.append(expr_token)
                else:
                    new_values.append(filter_value)
                    
            sg_filter["values"] = new_values
        
        # make a filters that the entity object expects
        entity_filter = {}
        entity_filter["logical_operator"] = "and"
        entity_filter["conditions"] = filters
        
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
    
    
    def __resolve_shotgun_filters(self, sg_data):
        """
        Replace Token instances in the filters with a real value from the tokens dictionary.

        This method processes the filters dictionary and replaces tokens with data found
        in the tokens dictionary. It returns a resolved filter dictionary that can be passed to 
        a shotgun query.
        """
        # TODO: Support nested conditions
        resolved_filters = copy.deepcopy(self._filters)
        for condition in resolved_filters["conditions"]:
            vals = condition["values"]
            if vals[0] and isinstance(vals[0], FilterExpressionToken):
                # we got a $filter! - replace with resolved value
                expr_token = vals[0]
                vals[0] = expr_token.resolve_shotgun_data(sg_data)                
        return resolved_filters
    
    def get_entity_type(self):
        """
        returns the shotgun entity type for this node
        """
        return self._entity_type
    
    def _should_item_be_processed(self, engine_str):
        """
        Checks if this node should be processed, given its deferred status.        
        """
        # check our special condition - is this node set to be auto-created with its parent node?
        if self._create_with_parent == False:
            return False
        
        # base class implementation
        return super(Entity, self)._should_item_be_processed(engine_str)
    
    def _create_folders_impl(self, io_receiver, parent_path, sg_data):
        """
        Creates folders.
        """
        items_created = []
        
        for entity in self.__get_entities(sg_data):

            # generate the field name
            folder_name = self._entity_expression.generate_name(entity)
            my_path = os.path.join(parent_path, folder_name)
                        
            # call out to callback
            self._create_folder(io_receiver, my_path)

            # copy files across
            self._copy_files_to_folder(io_receiver, my_path)

            # write to path cache db
            # note - assuming there is a code for every entity type here except project and task
            if self._entity_type == "Project":
                cache_name = entity["name"]
            elif self._entity_type == "Task":
                cache_name = entity["content"]
            elif self._entity_type == "HumanUser":
                cache_name = entity["login"]
            else:
                cache_name = entity["code"]
            
            io_receiver.add_entry_to_cache_db(my_path, self._entity_type, entity["id"], cache_name)
            
            # create a new entity dict including our own data and pass it down to children
            my_sg_data = copy.deepcopy(sg_data)
            my_sg_data_key = FilterExpressionToken.sg_data_key_for_folder_obj(self)
            my_sg_data[my_sg_data_key] = { "type": self._entity_type, "id": entity["id"] }
            
            items_created.append( (my_path, my_sg_data) )
            
        return items_created
    
    def _create_folder(self, io_receiver, path):
        """
        Helper method that wraps around the folder creation 
        so that it can be easily subclassed.
        """    
        # call out to callback
        io_receiver.make_folder(path)

    def __get_entities(self, sg_data):
        """
        Returns shotgun data for folder creation
        """
        # first check the constraints: if tokens contains a type/id pair our our type,
        # we should only process this single entity. If not, then use the query filter
        
        # first, resolve the filter queries for the current ids passed in via tokens
        resolved_filters = self.__resolve_shotgun_filters(sg_data)
        
        # see if the sg_data dictionary has anything for us
        my_sg_data_key = FilterExpressionToken.sg_data_key_for_folder_obj(self)
        if my_sg_data_key in sg_data:
            # we have a constraint!
            entity_id = sg_data[my_sg_data_key]["id"]
            # add the id constraint to the filters
            resolved_filters["conditions"].append({ "path": "id", "relation": "is", "values": [entity_id] })
            # get data - can be None depending on external filters

        # figure out which fields to retrieve
        fields = self._entity_expression.get_shotgun_fields()
        
        if self._entity_type == "Project":
            fields.add("name")
        elif self._entity_type == "Task":
            fields.add("content")
        elif self._entity_type == "HumanUser":
            fields.add("login")
        else:
            fields.add("code")
            
        if self._entity_type == "Step":
            fields.add("entity_type")
        
        # now find all the items (e.g. shots) matching this query
        entities = self._tk.shotgun.find(self._entity_type, resolved_filters, fields)
        
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
            rec = sg.find_one(self._entity_type, [ ["id", "is", my_id] ], fields_to_retrieve)
            if not rec:
                raise TankError("Could not find entity %s:%s in Shotgun as required by "
                                "the folder creation setup" % (self._entity_type, my_id))
            
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

        # validate
        if sg_name_expression is None:
            raise TankError("Missing name token in yml metadata file %s" % full_path )

        
        return UserWorkspace(tk, parent, full_path, metadata, sg_name_expression)
    
    
    def __init__(self, tk, parent, full_path, metadata, field_name_expression):
        """
        constructor
        """
        
        # this query confirms that there is a matching HumanUser in shotgun for the local login
        # This means that a query for the user happens twice, here and later during _get_entities
        # TODO possibly keep the result from this query instead and remove the later, duplicate, one
        user = login.get_shotgun_user(tk.shotgun) 

        if not user:
            msg = "Could not find a HumanUser in shotgun with login matching the local login. "
            msg += "Check that the local login corresponds to a user in shotgun."
            raise TankError(msg)

        filters = { "logical_operator": "and",
                     "conditions": [ { "path": "id", "relation": "is", "values": [ user["id"] ] } ] 
                  }
        
        Entity.__init__(self, 
                        tk,
                        parent, 
                        full_path,
                        metadata,
                        "HumanUser", 
                        field_name_expression, 
                        filters, 
                        create_with_parent=True)


class Project(Entity):
    """
    The root point. Represents a shotgun project.
    """
    
    @classmethod
    def create(cls, tk, project_path, metadata, project_data_root):
        """
        Factory method for this class
        """
        return Project(tk, project_path, metadata, project_data_root)
    
    
    def __init__(self, tk, project_path, metadata, project_data_root):
        """
        constructor
        """
                
        no_filters = {
            "logical_operator": "and",
            "conditions": []
        }
        
        self._tk = tk
        self._project_data_root = project_data_root
        
        # note! create_with_parent is set specifically to True
        # to make sure that we can bootstrap the folder creation 
        # process correctly. Folder creation always starts with 
        # a project node and setting create with parent to True
        # means that we are forcing it to always be processed.
        Entity.__init__(self, 
                        tk,
                        None, 
                        project_path,
                        metadata,
                        "Project", 
                        "tank_name", 
                        no_filters, 
                        create_with_parent=True)
                
    def get_data_root(self):
        """
        Returns the data root folder for this project
        """
        return self._project_data_root
        

    def _create_folder(self, io_receiver, path):
        """
        Project specific implementation of the folder creation.
        """
        io_receiver.prepare_project_root(path)
        




