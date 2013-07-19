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
Core hook which handles conversion of shotgun field data into strings.

This hook can be used to control how folders are named on disk given 
a field in shotgun. Should for example spaces be replaced by underscores
or periods when folders are created?

Also this conversion hook may raise exceptions in order to indicate a validation, 
for example if an invalid naming convention is being used.
"""

from tank import Hook
from tank import TankError
import re

class ProcessFolderName(Hook):

    def execute(self, entity_type, entity_id, field_name, value, **kwargs):
        """
        Default implementation. The following parameters are passed:
        
        * entity_type: the shotgun entity type for which the value is taken
        * entity_id: The entity id representing the data
        * field_name: the shotgun field associated with the value
        * value: the actual value in some form, as returned by shotgun        
        
        Generates a string value given some shotgun value.
        Doing smart conversions, so that for example
        a {"type":"Shot", "id":123, "name":"foo"} ==> "foo"
        """
        
        
        if value.__class__ == dict and "name" in value:
            # it is a dictionary with a name key - assume this is what we want
            # this is normally an entity link
            #
            # {"type":"Shot", "id":123, "name":"foo"} ==> "foo"
            #
            str_value = str(value["name"])
            
        elif value.__class__ == list and len(value) == 0:
            # this an empty list.
            #
            # [] ==> ""
            #
            str_value = ""
            
        elif value.__class__ == list and len(value) > 0:
            # this is a multi entity link with at least one element
            # that element is a dict with a name field
            # e.g. this is a multi entity link field
            # make a string by concatenating all names with _
            #
            # [{"name":"foo"}, {"name":"bar"}] ==> "foo_bar"
            #
            try:
                str_value = "_".join( [x["name"] for x in value] )
            except KeyError:
                str_value = str(value)
        
        else:
            # assume all other value types convert straight
            str_value = str(value)
            
        # replace white space with dashes
        str_value = re.sub("\W", "-", str_value) 

        # validation can be implemented by raising an exception:        
        #
        #if entity_type == "Shot" and str_value.startswith("AA"):
        #    raise TankError("Shot names cannot start with AA!")
        #
        
        return str_value
