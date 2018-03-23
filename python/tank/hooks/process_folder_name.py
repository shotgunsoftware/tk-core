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
for example if an invalid naming convention is being used:

if entity_type == "Shot" and str_value.startswith("AA"):
   raise TankError("Shot names cannot start with AA!")

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
        
        elif isinstance(value, basestring):
            # no conversion required
            str_value = value
            
        else:
            # assume all other value types convert to
            # a string
            str_value = str(value)
            
        # replace all non-alphanumeric characters with dashes, 
        # except for the project entity, where here are special rules
        is_project_name = (entity_type == "Project")
        str_value = self._replace_non_alphanumeric(str_value, is_project_name)
        
        return str_value
    
    def _replace_non_alphanumeric(self, src, is_project_name):
        """
        Safely replace all non-alphanumeric characters 
        with dashes (-).
        
        Note, this handles non-ascii characters correctly
        """
        
        if is_project_name:
            # regex to find non-word characters, except slashes and periods, which are preserved
            exp = re.compile(u"[^\w/\.]", re.UNICODE)
        else:
            # regex to find non-word characters - in ascii land, that is [^A-Za-z0-9_]
            # note that we use a unicode expression, meaning that it will include other
            # "word" characters, not just A-Z.  
            exp = re.compile(u"\W", re.UNICODE)
        
        if isinstance(src, unicode):
            # src is unicode so we don't need to convert!
            return exp.sub("-", src)
        else:
            # assume utf-8 encoding so decode, replace
            # and re-encode the returned result
            u_src = src.decode("utf-8")
            return exp.sub("-", u_src).encode("utf-8")
    
