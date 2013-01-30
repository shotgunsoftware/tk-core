"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Utilities relating to shotgun entities 
"""

import copy
import re

from ..platform import constants
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
    
    :param tk: tank api instance
    :param sg_entity_type: the shotgun entity type e.g. 'Shot'
    :param sg_id: The shotgun id for the record, e.g 1234
    :param sg_field_name: The field to generate value for, e.g. 'sg_sequence'
    :param data: The shotgun entity data chunk that should be converted to a string.
    """
    # call out to core hook
    return tk.execute_hook(constants.PROCESS_FOLDER_NAME_HOOK_NAME, 
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
        self._name_expr = field_name_expr
        
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
                # find all field names ["xx", "yy", "zz.xx"] from "{xx}_{yy}_{zz.xx}"
                self._fields.update(re.findall('{([^}^{]*)}', self._name_expr))
            except Exception, error:
                raise TankError("Could not parse the configuration field '%s' - Error: %s" % (self._name_expr, error) )
    
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
        
        Assumes the name will be used as a folder name and validates
        that the evaluated expression is suitable for disk use.
        
        :param values: dictionary of values to use 
        :returns: fully resolved name string
        """
        # convert shotgun values to string values
        
        str_data = {}
        
        # get the shotgun id from the shotgun entity dict
        sg_id = values.get("id")
        
        # first make sure that each field is valid
        for field_name in self._fields:
            
            
            if field_name not in values:
                # required value was not provided!
                raise TankError("Folder Configuration Error: "
                                "A Shotgun field '%s' is being requested as part of the expression "
                                "'%s' when creating folders connected to entities of type %s, "
                                "however no such field exists in Shotgun. Please review your "
                                "configuration!" % (field_name, self._name_expr, self._entity_type))
            
            raw_val = values.get(field_name)
            if raw_val is None:
                
                # try to make a nice name from values
                if "code" in values:
                    nice_name = "%s %s (id %s)" % (self._entity_type, values["code"], sg_id)
                else:
                    nice_name = "%s %s" % (self._entity_type, sg_id)
                
                raise TankError("Folder Configuration Error. Could not create folders for %s! "
                                "A Shotgun field '%s' is being requested as part of the expression "
                                "'%s' when creating folders connected to entities of type %s. "
                                "The folder for %s you are trying to create has a Null value in "
                                "this field and can therefore "
                                "not be created. " % (nice_name, field_name, self._name_expr, self._entity_type, nice_name))
                
            
            # now cast the value to a string
            str_data[field_name] = sg_entity_to_string(self._tk, self._entity_type, sg_id, field_name, raw_val)
            
        
        # change format from {xxx} to $(xxx)s for value substitution.
        adjusted_expr = self._name_expr.replace("{", "%(").replace("}", ")s")

        # just to be sure, make sure to catch any exceptions here
        # and produce a more sensible error message.
        try:
            val = adjusted_expr % (str_data)
        except Exception, error:
            raise TankError("Could not populate values for the expression '%s' - please "
                            "contact support! Error message: %s. "
                            "Data: %s" % (self._name_expr, error, str_data))
            
            
        # now validate the entire value!
        if re.match(constants.VALID_SG_ENTITY_NAME_REGEX, val) is None:
            # not valid!!!
            msg = ("The format string '%s' used in the Tank configuration "
                   "does not generate a valid folder name ('%s')! Valid "
                   "values are %s." % (self._name_expr, val, constants.VALID_SG_ENTITY_NAME_EXPLANATION))
            raise TankError(msg)        
            
        return val


