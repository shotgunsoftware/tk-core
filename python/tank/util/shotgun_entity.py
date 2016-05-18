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
Utilities relating to shotgun entities 
"""

import copy
import re

from . import constants
from ..errors import TankError


def sg_entity_to_string(tk, sg_entity_type, sg_id, sg_field_name, data):
    """
    Generates a string value given a shotgun value.
    This logic is in a hook but it typically does conversions such as:
    
    * "foo" ==> "foo"
    * {"type":"Shot", "id":123, "name":"foo"} ==> "foo"
    * 123 ==> "123"
    * [{"type":"Shot", "id":1, "name":"foo"}, {"type":"Shot", "id":2, "name":"bar"}] ==> "foo_bar"
    
    This method may also raise exceptions in the case the string value is not valid.
    
    :param tk: Sgtk api instance
    :param sg_entity_type: the shotgun entity type e.g. 'Shot'
    :param sg_id: The shotgun id for the record, e.g 1234
    :param sg_field_name: The field to generate value for, e.g. 'sg_sequence'
    :param data: The shotgun entity data chunk that should be converted to a string.
    """
    # call out to core hook
    return tk.execute_core_hook(constants.PROCESS_FOLDER_NAME_HOOK_NAME, 
                                entity_type=sg_entity_type, 
                                entity_id=sg_id,
                                field_name=sg_field_name,
                                value=data)


class EntityExpression(object):
    """
    Represents a name expression for a shotgun entity.
    A name expression converts a pattern and a set of shotgun data into a string:
      
    Expression                 Shotgun Entity Data                          String Result
    ----------------------------------------------------------------------------------------
    * "code"                 + {"code": "foo_bar"}                      ==> "foo_bar"
    * "{code}_{asset_type}"  + {"code": "foo_bar", "asset_type": "car"} ==> "foo_bar_car" 
    
    Optional fields are [bracketed]:
    
    * "{code}[_{asset_type}]" + {"code": "foo_bar", "asset_type": "car"} ==> "foo_bar_car"
    * "{code}[_{asset_type}]" + {"code": "foo_bar", "asset_type": None} ==> "foo_bar"
    
    It it is always connected to a specific shotgun entity type and 
    the fields need to be shotgun fields that exists for that entity type.
    """
    
    def __init__(self, tk, entity_type, field_name_expr):
        """
        Constructor.
        
        :param entity_type: the shotgun entity type this is connected to
        :param field_name_expr: string representing the expression
        """
        
        self._tk = tk
        self._entity_type = entity_type
        self._field_name_expr = field_name_expr
        
        # now validate
        if "{" not in field_name_expr:
            # simple form - surround with brackets to turn into a expression
            field_name_expr = "{%s}" % field_name_expr
        
        # now get all permutations for expressions with optional fields
        expr_variations = self._get_expression_variations(field_name_expr)

        # We want them most inclusive(longest) version first
        self._sorted_exprs = sorted(expr_variations, cmp=lambda x, y: cmp(len(x), len(y)), reverse=True)

        # now extract and store a bunch of data for each variation.
        self._variations = {}
        for v in expr_variations:
            
            try:            
                # find all field names ["xx", "yy", "zz.xx"] from "{xx}_{yy}_{zz.xx}"
                fields = set(re.findall('{([^}^{]*)}', v))
            except Exception, error:
                raise TankError("Could not parse the configuration field '%s' - Error: %s" % (field_name_expr, error) )

            # now look for any field which contains a dot - these are all deep links.
            # for example: sg_sequence.Sequence.code
            # extract the actual link field from each one and put in entity_links set
            # (in the above case, that would be sg_sequence)
            entity_links = set()
            for field in fields:
                if "." in field:
                    entity_links.add( field.split(".")[0] )
                
            # add this to our variations dict
            self._variations[v] = {"entity_links": entity_links, "fields": fields}
                
    
    def _get_expression_variations(self, definition):
        """
        Returns all possible optional variations for an expression.
        
        "{manne}"               ==> ['{manne}']
        "{manne}_{ludde}"       ==> ['{manne}_{ludde}']
        "{manne}[_{ludde}]"     ==> ['{manne}', '{manne}_{ludde}']
        "{manne}_[{foo}_{bar}]" ==> ['{manne}_', '{manne}_{foo}_{bar}']
        
        """
        # split definition by optional sections
        tokens = re.split("(\[[^]]*\])", definition)
        # seed with empty string
        definitions = ['']
        for token in tokens:
            temp_definitions = []
            # regex return some blank strings, skip them
            if token == '':
                continue
            if token.startswith('['):
                # check that optional contains a key
                if not re.search("{*[a-zA-Z_ 0-9]+}", token): 
                    raise TankError("Optional sections must include a key definition.")
                # Add definitions skipping this optional value
                temp_definitions = definitions[:]
                # strip brackets from token
                token = re.sub('[\[\]]', '', token)
            # check non-optional contains no dangleing brackets
            if re.search("[\[\]]", token): 
                raise TankError("Square brackets are not allowed outside of optional section definitions.")
            # make defintions with token appended
            for definition in definitions:
                temp_definitions.append(definition + token)
            definitions = temp_definitions
        return definitions
    
    
    def get_shotgun_fields(self):
        """
        Returns the shotgun fields that are needed in order to 
        build this name expression. Returns all fields, including optional.
        
        :returns: set of shotgun field names
        """        
        # use the longest exprssion - this contains the most fields
        longest_expr = self._sorted_exprs[0]
        return copy.copy(self._variations[longest_expr]["fields"])
    
    def get_shotgun_link_fields(self):
        """
        Returns a list of all entity links that are used in the name expression, 
        including optional ones.
        For example, if a name expression for a Shot is {code}_{sg_sequence.Sequence.code},
        the link fields for this expression is sg_sequence. 
        """
        longest_expr = self._sorted_exprs[0]
        return copy.copy(self._variations[longest_expr]["entity_links"])

    def generate_name(self, values):
        """
        Generates a name given some fields.
        
        Assumes the name will be used as a folder name and validates
        that the evaluated expression is suitable for disk use.
        
        :param values: dictionary of values to use 
        :returns: fully resolved name string
        """
                
        # first make sure that each field is valid
        for field_name in self.get_shotgun_fields():
            if field_name not in values:
                # required value was not provided!
                raise TankError("Folder Configuration Error: "
                                "A Shotgun field '%s' is being requested as part of the expression "
                                "'%s' when creating folders connected to entities of type %s, "
                                "however no such field exists in Shotgun. Please review your "
                                "configuration!" % (field_name, self._field_name_expr, self._entity_type))
            
        # ok all fields are there. But some values may be none. Try to resolve our expression against
        # the values, starting with the longest expression first.
        for expr in self._sorted_exprs:
            val = self._generate_name(expr, values)
            if val is not None:
                # name generation worked! - do not try alternative (shorter) expressions
                break
        
        if val is None:
            # completely failed to generate a name because of missing fields.
            
            # try to make a nice descriptive name if possible
            if "code" in values:
                nice_name = "%s %s (id %s)" % (self._entity_type, values["code"], values["id"])
            else:
                nice_name = "%s %s" % (self._entity_type, values["id"])
            
            raise TankError("Folder Configuration Error. Could not create folders for %s! "
                            "The expression %s refers to one or more values that are blank "
                            "in Shotgun and a folder can therefore "
                            "not be created." % (nice_name, self._field_name_expr))
        
        return val 

    
    def _generate_name(self, expression, values):
        """
        Generates a name given some fields.
        
        Assumes the name will be used as a folder name and validates
        that the evaluated expression is suitable for disk use.
        
        :param values: dictionary of values to use 
        :returns: fully resolved name string
        """

        fields = self._variations[expression]["fields"]
        
        # convert shotgun values to string values
        str_data = {}
        
        # get the shotgun id from the shotgun entity dict
        sg_id = values.get("id")
        
        # first make sure that each field is valid
        for field_name in fields:
            # get value from shotgun data dict
            raw_val = values.get(field_name)
            if raw_val is None:
                # cannot resolve this!
                return None
                
            # now cast the value to a string
            str_data[field_name] = sg_entity_to_string(self._tk, self._entity_type, sg_id, field_name, raw_val)
            
        
        # change format from {xxx} to %(xxx)s for value substitution.
        adjusted_expr = expression.replace("{", "%(").replace("}", ")s")

        # just to be sure, make sure to catch any exceptions here
        # and produce a more sensible error message.
        try:
            val = adjusted_expr % (str_data)
        except Exception, error:
            raise TankError("Could not populate values for the expression '%s' - please "
                            "contact support! Error message: %s. "
                            "Data: %s" % (expression, error, str_data))
            
        # now validate the entire value!
        if not self._validate_name(val):
            # not valid!!!
            msg = ("The format string '%s' used in the configuration "
                   "does not generate a valid folder name ('%s')! Valid "
                   "values are %s." % (expression, val, constants.VALID_SG_ENTITY_NAME_EXPLANATION))
            raise TankError(msg)      
            
        return val

    def _validate_name(self, name):
        """
        Check that the name meets basic file system naming standards.
        """    
        
        if self._entity_type == "Project":
            # allow slashes in project names
            exp = re.compile(constants.VALID_SG_PROJECT_NAME_REGEX, re.UNICODE)
        else:
            exp = re.compile(constants.VALID_SG_ENTITY_NAME_REGEX, re.UNICODE)    
        
        if isinstance(name, unicode):
            return bool(exp.match(name))
        else:
            # try decoding from utf-8:
            u_name = name.decode("utf-8")
            return bool(exp.match(u_name))

