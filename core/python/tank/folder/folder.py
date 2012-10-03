"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Folder Classes representing various types of dynamic behaviour 
"""
import os
import copy
import string
import re

from tank_vendor import yaml

from ..platform import constants
from ..errors import TankError
from .. import root

class Folder(object):
    """
    Base class for all other folder classes.
    (This should not be used in any configuration)
    """
    
    def __init__(self, parent, schema_name):
        """
        Constructor
        """
        self.children = []
        self.schema_name = schema_name
        self.parent = parent
        self.files = []
        
        if self.parent:
            # add me to parent!
            self.parent.add_child(self)
            
    def add_child(self, child):
        """
        Adds a child to the list of children that each node keeps.
        """
        self.children.append(child)
        
    def add_file(self, path):
        """
        Adds a file name that should be added to this folder as part of processing.
        The file path should be absolute.
        """
        self.files.append(path)
                
    def find_entity_folders(self, entity_type):
        """
        Recursively scans all items in the tree, looking for 
        entity folders of the given entity type. Returns a list of those objects
        """
        found_entities = list()
        
        for child in self.children:
            if isinstance(child, Entity) and child.entity_type == entity_type:
                # @todo: note! once we have found the type we are looking for, 
                # we abort the recursion. This means that we cannot handle
                # assets/sub assets at the moment.
                found_entities.append(child)
            else:
                # process children
                found_child = child.find_entity_folders(entity_type)
                found_entities.extend(found_child)
        
        return found_entities
    
    def create_folders(self, schema, path, tokens, explicit_child_list=None):
        """
        Recursive folder creation. Creates folders for this node and one/all
        of its children. If explicit_child_list is passed in, we will pop the last
        item in the list and process it. Otherwise, we will process all of our
        children and end recursion if we reach a new Entity folder where
        create_with_parent is False.
        
        :param schema: the main schema object
        :param path: the parent path
        :param tokens: resolved tokens
        :param explicit_child_list: a list of Folder instances to visit
        :returns: Nothing
        """
        raise NotImplementedError
    
    def _copy_files_to_folder(self, schema, path):
        """
        Helper.
        Copies all files that have been registered with this folder object
        to a specific target folder on disk, using the dedicated hook
        """
        for src_file in self.files:
            target_path = os.path.join(path, os.path.basename(src_file))
            schema.copy_file(src_file, target_path)

    def _create_child_folders(self, schema, path, tokens, explicit_child_list=None):
        """
        Helper method to create this folder's children. If explicit_child_list is passed
        we will pop the last element of the list and process just that single
        folder. Otherwise, we'll process all child folders.
        
        :param schema: the main schema object
        :param path: the parent path
        :param tokens: resolved tokens
        :param explicit_child_list: a list of Folder instances to visit
        :returns: Nothing
        """
        if explicit_child_list:
            # We're going to modify the list, so make a copy.
            my_child_list = copy.deepcopy(explicit_child_list)
            child = my_child_list.pop()
            child.create_folders(schema, path, tokens, my_child_list)
        else:
            for child in self.children:
                if isinstance(child, Entity) and not child.create_with_parent:
                    # don't create child Entity folders unless the create_with_parent flag is on
                    process_children = False
                else:
                    # for all other cases, process children even though recurse is off:
                    # static folders, steps and tasks
                    process_children = True
            
                if process_children:
                    child.create_folders(schema, path, tokens, explicit_child_list)

################################################################################################

class Static(Folder):
    """
    Represents a static folder in the file system
    """
    
    def __init__(self, parent, name):
        """
        The name parameter represents the folder name that will be created in the file system.
        """
        Folder.__init__(self, parent, name)
        self.name = name
    
    def create_folders(self, schema, path, tokens, explicit_child_list=None):
        """
        Creates a static folder and its children

        :param schema: Parent schema.
        :type  schema: Schema
        :param path: Parent path.
        :type  path: String.
        :param tokens: Tokens to process
        :param explicit_child_list: A list of Folder instances to visit
        """
        # create our folder
        my_path = os.path.join(path, self.name)
        
        # call out to callback
        schema.make_folder(my_path, None)

        # copy files across
        self._copy_files_to_folder(schema, my_path)
        
        # create children
        self._create_child_folders(schema, my_path, tokens, explicit_child_list)

################################################################################################

class ListField(Folder):
    """
    Represents values from a Shotgun list field in the file system (like Asset.sg_asset_type)
    """

    def __init__(self, parent, entity_type, field_name, skip_unused):
        self.entity_type = entity_type
        self.field_name = field_name
        self.token_name = "%s.%s" % (entity_type, field_name)
        self.skip_unused = skip_unused
        
        Folder.__init__(self, parent, self.token_name)
        
    def create_folders(self, schema, path, tokens, explicit_child_list=None):
        """
        Create folders for one or all list field values and recurse down
        """
        
        # First check the constraints: if tokens contains a matching value, only create a single
        # folder. Otherwise, create folders for all list field values.
        if self.token_name in tokens:
            values = [tokens[self.token_name]]
        else:
            # TODO: handle no response
            resp = schema.sg.schema_field_read(self.entity_type, self.field_name)
            values = resp[self.field_name]["properties"]["valid_values"]["value"]

            if self.skip_unused:
                values = self._filter_unused_list_values(schema.sg, values, tokens.get("Project"))
        
        # process each value independently
        for value in values:
            my_path = os.path.join(path, value)
            schema.make_folder(my_path, None)
            
            # copy files across
            self._copy_files_to_folder(schema, my_path)
            
            # create a new tokens dict including our own data and pass it down to children
            my_tokens = copy.deepcopy(tokens)
            my_tokens[self.token_name] = value
            
            # create children
            self._create_child_folders(schema, my_path, my_tokens, explicit_child_list)
        
    def _filter_unused_list_values(self, sg, values, project):
        """
        Remove values which are not used by entities in this project.
        """
        used_values = []
        filters = [[self.field_name, 'is', None]]

        if project:
            filters.append(['project', 'is', project])

        for value in values:
            filters[0][2] = value
            summary = sg.summarize(self.entity_type, filters, [{'field':self.field_name, 'type': 'count'}])
            if summary.get("summaries", {}).get(self.field_name):
                used_values.append(value)

        return used_values

################################################################################################

class EntityName(object):
    """
    Represents a name expression for an entity in a configuration.
    
    A name expression can be on the form:
    
    * (simple) code
    * (advanced) {code}_{asset_type}
    
    It it is always connected to a specific shotgun entity type and 
    the fields need to be shotgun fields that exists for that entity type.
    """
    
    def __init__(self, entity_type, field_name_expr):
        """
        Constructor.
        
        :param entity_type: the shotgun entity type this is connected to
        :param field_name_expr: string representing the expression
        """
        
        self._entity_type = entity_type
        self._name_expr = field_name_expr
        formatter = string.Formatter()
        
        self._fields = set()
        
        # now validate
        if "{" not in self._name_expr:
            # simple form
            self._fields.add(self._name_expr)
            # surround with brackets to turn into a expression
            self._name_expr = "{%s}" % self._name_expr
        else:
            # expression
            try:            
                for format_info in formatter.parse(self._name_expr):
                    # the {xx} - token xx is in the second list index returned by parse
                    sg_field = format_info[1]
                    # sometimes a constant string is returning a None - meaning that it
                    # is not a {field} but just a normal static part of the string.
                    # need to check for this:
                    if sg_field is not None:
                        self._fields.add(sg_field)
            except Exception, error:
                raise TankError("Could not parse the configuration field '%s' - Error: %s" % (self._name_expr, error) )
    
        
    
    def validate(self, values):
        """
        Checks that the fields and the full path is valid and doesn't 
        produce a dodgy file name. raises an exception on failure,
        returns silently on success.
        
        :param values: dictionary of values to test
        """
        
        # first make sure that each field is valid
        for field_name in self._fields:
            raw_val = values.get(field_name)
            if raw_val is None:
                # required value was not provided!
                raise TankError("Folder Configuration Error: "
                                "A Shotgun field '%s' is being requested as part of the expression "
                                "'%s' when creating folders connected to entities of type %s, "
                                "however no such field exists in Shotgun. Please review your "
                                "configuration!" % (field_name, self._name_expr, self._entity_type))
            
            # now cast the value to a string
            val = generate_string_val(raw_val)
            
            # validate
            if re.match(constants.VALID_SG_ENTITY_NAME_REGEX, val) is None:
                # not valid!!!
                msg = ("The Shotgun field %s.%s is used in the Tank config. "
                       "However the %s value '%s' is not a valid value for a folder on disk so "
                       "the folder creation was aborted. Valid values are %s. "
                       "Please rename the value in Shotgun and try "
                       "again.\n" % (self._entity_type, 
                                   field_name, 
                                   self._entity_type, 
                                   val, 
                                   constants.VALID_SG_ENTITY_NAME_EXPLANATION))
                raise TankError(msg)        
        
        # now validate the entire value!
        val = self.generate_name(values)
        if re.match(constants.VALID_SG_ENTITY_NAME_REGEX, val) is None:
            # not valid!!!
            msg = ("The format string '%s' used in the Tank configuration "
                   "does not generate a valid folder name ('%s')! Valid "
                   "values are %s." % (self._name_expr, val, constants.VALID_SG_ENTITY_NAME_EXPLANATION))
            raise TankError(msg)        
        
    def get_shotgun_fields(self):
        """
        Returns the shotgun field that are needed in order to 
        build this name expression.
        
        :returns: set of shotgun field names
        """
        return copy.copy(self._fields)
    
    def generate_name(self, values):
        """
        Generates a name given some fields.
        
        :param values: dictionary of values to use 
        :returns: fully resolved name string
        """
        # convert shotgun values to string values
        
        str_data = {}
        adjustments = {}
        
        for key in values:
            # adjust the key to make sure we have to 
            # . characters since this confuses the parser.
            # so the SG field entity.Shot.code --> entity__Shot__code
            adjusted_field = key.replace(".", "__")

            # store the adjustments we are making so that we can
            # do the same adjustments to the expression later
            adjustments[key] = adjusted_field
            
            # and store all values in a dict
            str_data[adjusted_field] = generate_string_val(values[key])
            
        
        # now look at the expression ({code}_{entity.Shot.code}) and convert it
        # to adjusted values ( -->  {code}_{entity__Shot__code}
        # we do this by replacing all adjusted fields
        # TODO: there may be edge cases here where this replacement fails
        ajusted_expr = self._name_expr
        for key in adjustments:
            ajusted_expr = ajusted_expr.replace(key, adjustments[key])
        
        # just to be sure, make sure to catch any exceptions here
        # and produce a more sensible error message.
        try:
            formatter = string.Formatter()
            val = formatter.vformat(ajusted_expr, [], str_data)
        except Exception, error:
            raise TankError("Could not populate values for the expression '%s' - please "
                            "contact support! Error message: %s. "
                            "Data: %s" % (self._name_expr, error, str_data))
        return val
        

class Entity(Folder):
    """
    Represents an entity in Shotgun
    """
    
    def __init__(self, parent, entity_type, field_name_expression, filters, create_with_parent=False):
        """
        Constructor.
        
        
        The filter syntax for deciding which folders to create
        is a dictionary, often looking something like this:
        
             {
                 "logical_operator": "and",
                 "conditions": [ { "path": "project", "relation": "is", "values": [ Token("Project") ] } ]
             }
        
        
        This is basically a shotgun API filter dictionary, but with interleaved tokens 
        (e.g. the Token("Project")). Tank will resolve any Token fields prior to 
        passing the filter to Shotgun for evaluation.       
        
        :param parent: the parent object
        :param entity_type: shotgun entity type to connect to
        :param field_name_expression: shotgun field name expression to use as folder name
        :param filters: filter syntax - see above
        :param create_with_parent: True if this folder should be created at the same time as its parent folder
        """
        
        # the schema name is the same as the SG entity type
        Folder.__init__(self, parent, entity_type)
        
        self.entity_type = entity_type
        self.entity_name_obj = EntityName(self.entity_type, field_name_expression)
        self.filters = filters
        self.create_with_parent = create_with_parent
    
    
    def _fields_for_find(self):
        """
        Helper function.
        Returns the fields that we need to get from shotgun for a particular object
        in order to create a folder name
        """
        
        # get the fields needed by the field names
        fields = self.entity_name_obj.get_shotgun_fields()
        
        if self.entity_type == "Project":
            fields.add("name")
        elif self.entity_type == "Task":
            fields.add("content")
        elif self.entity_type == "HumanUser":
            fields.add("login")
        else:
            fields.add("code")
        
        if self.entity_type == "Step":
            fields.add("entity_type")
        
        return list(fields)

    def _resolve_tokens(self, filters, tokens):
        """
        Replace Token instances in the filters with a real value from the tokens dictionary.

        Filters are often on the form
        
         {
             "logical_operator": "and",
             "conditions": [ { "path": "project", "relation": "is", "values": [ Token("Project") ] } ]
         }

        This method processes the filters dictionary and replaces tokens with data found
        in the tokens dictionary. It returns a resolved filter dictionary that can be passed to 
        a shotgun query.
        """
        # TODO: Support nested conditions
        resolved_filters = copy.deepcopy(filters)
        for condition in resolved_filters["conditions"]:
            vals = condition["values"]
            if vals[0] and isinstance(vals[0], Token):
                if vals[0].key in tokens:
                    vals[0] = tokens[vals[0].key]
                else:
                    raise TokenError(vals[0].key)
        return resolved_filters
    
    
    def _create_folder(self, schema, path, entity):
        """
        Helper method. Creates path on disk + tank cache files.

        :param schema: the schema object (for callback access)
        :param path: the parent path
        :param entity: dictionary with all values that are needed for this item. This is typically
                       the id and the fields necessary for creating the name for this item.
                       
        :returns: the path created.
        """
        # validate the name
        self.entity_name_obj.validate(entity)
        
        # generate the field name
        folder_name = self.entity_name_obj.generate_name(entity)
                
        # create folder via callback
        my_path = os.path.join(path, folder_name)
        schema.make_folder(my_path, entity)
        
        # copy files across
        self._copy_files_to_folder(schema, my_path)
        
        # write to path cache db
        # note - assuming there is a code for every entity type here except project and task
        if self.entity_type == "Project":
            cache_name = entity["name"]
        elif self.entity_type == "Task":
            cache_name = entity["content"]
        elif self.entity_type == "HumanUser":
            cache_name = entity["login"]
        else:
            cache_name = entity["code"]
        
        schema.add_entry_to_cache_db(my_path, self.entity_type, entity["id"], cache_name)
        
        # tell the schema class that we created one
        schema.num_entity_folders += 1
        
        return my_path
    
    def _get_entities(self, schema, tokens):
        # first check the constraints: if tokens contains a type/id pair our our type,
        # we should only process this single entity. If not, then use the query filter
        
        # first, resolve the filter queries for the current ids passed in via tokens
        resolved_filters = self._resolve_tokens(self.filters, tokens) # TODO: Catch TokenError

        if self.entity_type in tokens:
            # we have a constraint!
            entity_id = tokens[self.entity_type]["id"]
            # add the id constraint to the filters
            resolved_filters["conditions"].append({ "path": "id", "relation": "is", "values": [entity_id] })
            # get data - can be None depending on external filters

        # now find all the items (e.g. shots) matching this query
        entities = schema.sg.find(self.entity_type, resolved_filters, self._fields_for_find())
        
        return entities
    
    def create_folders(self, schema, path, tokens, explicit_child_list=None):
        """
        Create folders for a specific entity or all entities matching the filters.
        Then, recurse to their child folders.
        """
        for entity in self._get_entities(schema, tokens):
            my_path = self._create_folder(schema, path, entity)
            
            # create a new entity dict including our own data and pass it down to children
            my_tokens = copy.deepcopy(tokens)
            my_tokens[self.entity_type] = { "type": self.entity_type, "id": entity["id"] }
            
            self._create_child_folders(schema, my_path, my_tokens, explicit_child_list)
    
    def extract_tokens(self, sg, tokens):
        """
        Special method used by the main schema visitor. 
        
        Updates the data structure passed around via the tokens variable. 
        
        Example: for a Shot folder with filters sg_sequence is Token("Sequence"), acquire
        the value of the sg_sequence for the current Shot and stick it in the tokens list.
        """
        
        # If we don't have an entry in tokens for the current entity type, then we can't
        # extract any tokens. Used by #17726.
        if not self.entity_type in tokens:
            return
            
        field_to_token_key_map = {}
        fields_to_retrieve = []
        
        # TODO: Support nested conditions
        for condition in self.filters["conditions"]:
            vals = condition["values"]
            
            # note the $FROM$ condition below - this is a bit of a hack to make sure we exclude
            # the special step based culling filter that is commonly used. Because steps are 
            # sort of free floating and not associated with an entity, removing them from the 
            # resolve should be fine in most cases.
            
            if vals[0] and isinstance(vals[0], Token) and not condition["path"].startswith('$FROM$'):
                fields_to_retrieve.append(condition["path"])
                field_to_token_key_map[condition["path"]] = vals[0].key
        
        # add some extra fields apart from the stuff in the config
        if self.entity_type == "Project":
            fields_to_retrieve.append("name")
        elif self.entity_type == "Task":
            fields_to_retrieve.append("content")
        else:
            fields_to_retrieve.append("code")
        
        # TODO: AND the id query with this folder's query to make sure this path is
        # valid for the current entity. Throw error if not so driver code knows to 
        # stop processing. This would be needed in a setup where (for example) Asset
        # appears in several locations in the filesystem and that the filters are responsible
        # for determining which location to use for a particular asset.
        my_id = tokens[self.entity_type]["id"]
        rec = sg.find_one(self.entity_type, [ ["id", "is", my_id] ], fields_to_retrieve)
        if not rec:
            raise TankError("Could not find entity %s:%s in Shotgun as required by "
                            "the folder creation setup" % (self.entity_type, my_id))
        
        # and append code which is always needed.
        name = None
        if self.entity_type == "Project":
            name = rec["name"]
            tokens[self.entity_type]["name"] = rec["name"]
        elif self.entity_type == "Task":
            name = rec["content"]
            tokens[self.entity_type]["content"] = rec["content"]
        else:
            name = rec["code"]
            tokens[self.entity_type]["code"] = rec["code"]
        
        
        for field in field_to_token_key_map:
            value = rec[field]
            token_key = field_to_token_key_map[field]
            
            if value:
                if isinstance(value, dict):
                    # If entity, check is type matches
                    if token_key == value.get("type", token_key):
                        tokens[token_key] = value
                else:
                        tokens[token_key] = value
            else:
                # field was none! - cannot handle that
                raise TankError("The %s %s has a required field %s that \ndoes not have a value "
                                "set in Shotgun. \nDouble check the values and try "
                                "again!\n" % (self.entity_type, name, field))    
    
    
################################################################################################

class Project(Entity):
    """
    The root point. Represnts a shotgun project.
    """
    
    def __init__(self, root_path):
        no_filters = {
            "logical_operator": "and",
            "conditions": []
        }
        
        Entity.__init__(self, None, "Project", "tank_name", no_filters)
        self.root_path = root_path

    def _create_folder(self, schema, path, entity):
        my_path = super(Project, self)._create_folder(schema, path, entity)

        # add non primary root config
        if my_path != schema.project_root:
            # make tank config directories
            tank_dir = os.path.join(my_path, "tank")
            schema.make_folder(tank_dir, None)
            config_dir = os.path.join(my_path, "tank", "config")
            schema.make_folder(config_dir, None)
            # write primary path 
            root.write_primary_root(config_dir, schema.project_root)
        return my_path

################################################################################################

class Token:
    """
    The token class is used to refer back to items in the filter syntax
    """
    def __init__(self, key):
        self.key = key


class TokenError(TankError):
    """
    Error thrown in process of resolving tokens.
    """
    pass

def generate_string_val(data):
    """
    Generates a string value given a shotgun value.
    Doing smart conversions, so that for example
    a {"type":"Shot", "id":123, "name":"foo"} ==> "foo"
    """
    if data.__class__ == dict and "name" in data:
        # it is a dictionary with a name key - assume this is what we want
        # this is normally an entity link
        str_data = str(data["name"])
    elif data.__class__ == list and len(data) == 0:
        # this an empty list.
        str_data = ""
    elif data.__class__ == list and len(data) > 0:
        # this is a multi entity link with at least one element
        # that element is a dict with a name field
        # e.g. this is a multi entity link field
        
        # make a string by concatenating all names with _
        # [{"name":"foo"}, {"name":"bar"}] ==> "foo_bar"
        try:
            str_data = "_".join( [x["name"] for x in data] )
        except KeyError:
            str_data = str(data)
    else:
        # assume all other data types convert straight
        str_data = str(data)
        
    # replace white space with dashes
    str_data = re.sub("\W", "-", str_data) 
    
    return str_data
