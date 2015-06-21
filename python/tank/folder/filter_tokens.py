# Copyright (c) 2015 Shotgun Software Inc.
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
from ..errors import TankError


class FilterToken(object):
    """
    Base class for all token objects that are used
    to dynamically represent objects in shotgun query
    expressions in the folder schema system. 
    
    An example of such an object is when you have a schema definition
    looking like this:
    
    {"path": "project", "relation": "is", "values": ["$project"]}
    
    In this case, $project is converted into a FilterExpression token
    that is resolved into a shotgun id at runtime. 
    """  
    
    def __init__(self):
        pass
    

class FilterExpressionToken(FilterToken):
    """
    Represents a $token in a filter expression for entity nodes.
    
    An example of such an object is when you have a schema definition
    looking like this:
    
    {"path": "project", "relation": "is", "values": ["$project"]}    
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
        
        # deferred import to avoid cyclic references
        from .folder_types import Entity, ListField, Static
        
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
        
        :param expression: Expression string, e.g. "$project"
        :param parent: parent object in the schema hierarchy. This is
                       an object deriving from the Folder base class.
        """
        # call base class
        FilterToken.__init__(self)

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
        
        :returns: entity_type as string
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




class CurrentStepExpressionToken(FilterToken):
    """
    Represents the current step.
    """
    
    def __init__(self, sg_task_step_link_field):
        """
        Constructor
        
        :param sg_task_step_link_field: The shotgun field which links a task to a step
        """
        # call base class
        FilterToken.__init__(self)
        
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
    

class CurrentTaskExpressionToken(FilterToken):
    """
    Represents the current task
    """
    
    def __init__(self):
        """
        Constructor
        """
        # call base class
        FilterToken.__init__(self)
    
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




class SymlinkToken(object):
    """
    Helper class.
    Represents a folder level in a symlink target.
    Please note that this object is unrelated to the FilterToken hierarchy.
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
