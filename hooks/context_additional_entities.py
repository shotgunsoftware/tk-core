"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Hook which provides advanced customization of context creation.
Returns a dict with two keys:

    entity_types_in_path: a list of Shotgun entity types (ie. CustomNonProjectEntity05) that
        context_from_path should recognize and use to fill its additional_entities list.
    
    entity_fields_on_task: a list of Shotgun fields (ie. sg_extra_link) on the Task entity
        that context_from_entity should query Shotgun for and insert the resulting entities
        into its additional_entities_list.

"""

from tank import Hook

class ContextAdditionalEntities(Hook):

    def execute(self, **kwargs):
        """
        The default implementation does not do anything.
        """
        
        val = {
            "entity_types_in_path": [],
            "entity_fields_on_task": []
        }
        
        return val
