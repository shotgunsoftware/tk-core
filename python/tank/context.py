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
Management of the current context, e.g. the current shotgun entity/step/task.

"""

import os
import pickle
import copy

from tank_vendor import yaml

from .util import login
from .util import shotgun_entity
from .util import shotgun
from .errors import TankError
from .path_cache import PathCache
from .template import TemplatePath


class Context(object):
    """
    Class which captures the current point in both shotgun and the file system which a
    particular engine is connected to.

    Each engine is bound to a context - the context points the engine to a particular
    point in shotgun and on disk - it could be something as detailed as a task inside a Shot,
    and something as vague as simply an empty context.

    Typically, for tank to function at its most basic level, the project needs to be known.
    Otherwise (if the context object is empty), it merely becomes an indication of the fact
    that Tank doesn't understand what the context is pointing at.

    Contexts are always created via the factory methods. Avoid instantiating it by hand.

    """

    def __init__(self, tk, project=None, entity=None, step=None, task=None, user=None, additional_entities=None):
        """
        Do not create instances of this class directly.
        Instead, use the factory methods.
        """
        self.__tk = tk
        self.__project = project
        self.__entity = entity
        self.__step = step
        self.__task = task
        self.__user = user
        self.__additional_entities = additional_entities or []
        self._entity_fields_cache = {}

    def __repr__(self):
        # multi line repr
        msg = []
        msg.append("  Project: %s" % str(self.__project))
        msg.append("  Entity: %s" % str(self.__entity))
        msg.append("  Step: %s" % str(self.__step))
        msg.append("  Task: %s" % str(self.__task))
        msg.append("  User: %s" % str(self.__user))
        msg.append("  Shotgun URL: %s" % self.shotgun_url)
        msg.append("  Additional Entities: %s" % str(self.__additional_entities))
        
        return "<Sgtk Context: %s>" % ("\n".join(msg))

    def __str__(self):
        # smart looking string representation
        
        if self.project is None:
            # empty context!
            ctx_name = "Empty Context"
        
        elif self.entity is None:
            # project-only!
            ctx_name = "%s" % self.project.get("name")
        
        elif self.step is None and self.task is None:
            # entity only
            # e.g. Shot ABC_123
            
            # resolve custom entities to their real display
            entity_display_name = shotgun.get_entity_type_display_name(self.__tk, 
                                                                       self.entity.get("type"))
            
            ctx_name = "%s %s" % (entity_display_name, self.entity.get("name"))

        else:
            # we have either step or task
            task_step = None
            if self.step:
                task_step = self.step.get("name")
            if self.task:
                task_step = self.task.get("name")
            
            # e.g. Lighting, Shot ABC_123
            
            # resolve custom entities to their real display
            entity_display_name = shotgun.get_entity_type_display_name(self.__tk, 
                                                                       self.entity.get("type"))
            
            ctx_name = "%s, %s %s" % (task_step, 
                                      entity_display_name, 
                                      self.entity.get("name"))
        
        return ctx_name

    def __eq__(self, other):
        """
        Test if this Context instance is equal to the other Context instance
                        
        :param other:   The other Context instance to compare with
        :returns:       True if self represents the same context as other, 
                        otherwise False
        """
        def _entity_dicts_eq(d1, d2):
            """
            Test to see if two entity dictionaries are equal.  They are considered
            equal if both are dictionaries containing 'type' and 'id' with the same
            values for both keys, For example:
            
            Comparing these two dictionaries would return True:
            - {"type":"Shot", "id":123, "foo":"foo"}
            - {"type":"Shot", "id":123, "foo":"bar", "bar":"foo"}
            
            But comparing these two dictionaries would return False:
            - {"type":"Shot", "id":123, "foo":"foo"}
            - {"type":"Shot", "id":567, "foo":"foo"} 
    
            :param d1:  First entity dictionary
            :param d2:  Second entity dictionary
            :returns:   True if d1 and d2 are considered equal, otherwise False.
            """
            if d1 == d2 == None:
                return True
            if d1 == None or d2 == None:
                return False
            return d1["type"] == d2["type"] and d1["id"] == d2["id"]        
        
        if not isinstance(other, Context):
            return NotImplemented

        if not _entity_dicts_eq(self.project, other.project):
            return False
        
        if not _entity_dicts_eq(self.entity, other.entity):
            return False
        
        if not _entity_dicts_eq(self.step, other.step):
            return False
        
        if not _entity_dicts_eq(self.task, other.task):
            return False
        
        # compare additional entities
        if self.additional_entities and other.additional_entities:
            # compare type, id tuples of all additional entities to ensure they are exactly the same.
            # this compare ignores duplicates in either list and just ensures that the intersection
            # of both lists contains all unique elements from both lists. 
            types_and_ids = set([(e["type"], e["id"]) for e in self.additional_entities if e])
            other_types_and_ids = set([(e["type"], e["id"]) for e in other.additional_entities if e])
            if types_and_ids != other_types_and_ids:
                return False
        elif self.additional_entities or other.additional_entities:
            return False

        # finally compare the user - this may result in a Shotgun look-up 
        # so do this last!
        if not _entity_dicts_eq(self.user, other.user):
            return False
        
        return True 

    def __ne__(self, other):
        """
        Test if this Context instance is not equal to the other Context instance
                        
        :param other:   The other Context instance to compare with
        :returns:       True if self != other, False otherwise
        """        
        is_equal = self.__eq__(other)
        if is_equal is NotImplemented:
            return NotImplemented
        return not is_equal

    def __deepcopy__(self, memo):
        """
        Allow Context objects to be deepcopied - Note that the tk
        member is _never_ copied
        """
        # construct copy with current api instance:
        ctx_copy = Context(self.__tk)
        
        # deepcopy all other members:
        ctx_copy.__project = copy.deepcopy(self.__project, memo)
        ctx_copy.__entity = copy.deepcopy(self.__entity, memo)
        ctx_copy.__step = copy.deepcopy(self.__step, memo)
        ctx_copy.__task = copy.deepcopy(self.__task, memo)
        ctx_copy.__user = copy.deepcopy(self.__user, memo)        
        ctx_copy.__additional_entities = copy.deepcopy(self.__additional_entities, memo)
        
        # except:
        # ctx_copy._entity_fields_cache
        
        return ctx_copy

    ################################################################################################
    # properties

    @property
    def project(self):
        """
        The shotgun project associated with this context.

        ``{'type': 'Project', 'id': 4, 'name': 'demo_project'}.``

        :returns: A std shotgun link dictionary.
                  May return None if this has not been defined
        """
        return self.__project


    @property
    def entity(self):
        """
        The shotgun entity associated with this context.

        ``{'type': 'Shot', 'id': 4, 'name': 'AAA_123'}.``

        :returns: A std shotgun link dictionary.
                  May return None if this has not been defined
        """
        return self.__entity

    @property
    def step(self):
        """
        The shotgun step associated with this context.

        ``{'type': 'Step', 'id': 1, 'name': 'Client'}``

        :returns: A std shotgun link dictionary.
                  May return None if this has not been defined
        """
        return self.__step

    @property
    def task(self):
        """
        The shotgun task associated with this context.

        ``{'type': 'Task', 'id': 212, 'name': 'first_pass_lgt'}``

        :returns: A std shotgun link dictionary.
                  May return None if this has not been defined
        """
        return self.__task

    @property
    def user(self):
        """
        The shotgun human user, associated with this context.
        
        ``{'type': 'HumanUser', 'id': 212, 'name': 'William Winter'}``

        :returns: A std shotgun link dictionary.
                  May return None if this has not been defined.
        """
        # NOTE! get_shotgun_user returns more fields than just type, id and name
        # so make sure we get rid of those. We should make sure we return the data
        # in a consistent way, similar to all other entities. No more. No less.
        if self.__user is None:
            user = login.get_current_user(self.__tk)
            if user is not None:
                self.__user = {"type": user.get("type"), 
                               "id": user.get("id"), 
                               "name": user.get("name")}
        return self.__user

    @property
    def additional_entities(self):
        """
        List of entities that are required to provide a full context in non-standard configurations.
        The "context_additional_entities" core hook gives the context construction code hints about
        how this data should be populated.

        :returns: A list of std shotgun link dictionaries.
                  Will be an empty list in most cases.
        """
        return self.__additional_entities

    @property
    def entity_locations(self):
        """
        A list of disk locations where the entity associated with this context can be found.
        """
        if self.entity is None:
            return []

        paths = self.__tk.paths_from_entity(self.entity["type"], self.entity["id"])

        return paths

    @property
    def shotgun_url(self):
        """
        Returns the shotgun detail page url that best represents this context. Depending on 
        the context, this may be a task, a shot, an asset or a project. If the context is 
        completely empty, the root url of the associated shotgun installation is returned.
        """
        
        # walk up task -> entity -> project -> site
        
        if self.task is not None:
            return "%s/detail/%s/%d" % (self.__tk.shotgun.base_url, "Task", self.task["id"])            
        
        if self.entity is not None:
            return "%s/detail/%s/%d" % (self.__tk.shotgun.base_url, self.entity["type"], self.entity["id"])            

        if self.project is not None:
            return "%s/detail/%s/%d" % (self.__tk.shotgun.base_url, "Project", self.project["id"])            
        
        # fall back on just the site main url
        return self.__tk.shotgun.base_url
        
    @property
    def filesystem_locations(self):
        """
        A list of filesystem locations associated with this context.
        """
        
        # first handle special cases: empty context
        if self.project is None:
            return []
        
        # first handle special cases: project context
        if self.entity is None:
            return self.__tk.paths_from_entity("Project", self.project["id"])
            
        # at this stage we know that the context contains an entity
        # start off with all the paths matching this entity and then cull it down 
        # based on constraints.
        entity_paths = self.__tk.paths_from_entity(self.entity["type"], self.entity["id"])
                
        # for each of these paths, get the context and compare it against our context
        # todo: optimize this!
        matching_paths = []
        for p in entity_paths:
            ctx = self.__tk.context_from_path(p)
            # the stuff we need to compare against are all the "child" levels
            # below entity: task and user
            matching = False
            if ctx.user is None and self.user is None:
                # no user data in either context
                matching = True
            elif ctx.user is not None and self.user is not None:
                # both contexts have user data - is it matching?
                if ctx.user["id"] == self.user["id"]:
                    matching = True
            
            if matching:
                # ok so user looks good, now check task.
                # it is possible that with a context that comes from shotgun
                # there is a task populated which is not being used in the file system
                # so when we compare tasks, only if there are differing task ids, 
                # we should treat it as a mismatch.
                task_matching = True
                if ctx.task is not None and self.task is not None:
                    if ctx.task["id"] != self.task["id"]:
                        task_matching = False
                
                if task_matching:
                    # both user and task is matching
                    matching_paths.append(p)
                    
        return matching_paths
                    
    @property
    def tank(self):
        """
        An Sgtk API instance
        """
        return self.__tk

    ################################################################################################
    # new name
    sgtk = tank

    ################################################################################################
    # public methods

    def as_template_fields(self, template):
        """
        Returns the context object as a dictionary of template fields.
        This is useful if you want to use a Context object as part of a call to the Sgtk API.

            >>> import sgtk
            >>> tk = sgtk.sgtk_from_path("/studio.08/demo_project/sequences/AAA/ABC/Lighting/work")
            >>> template = tk.templates['lighting_work']
            >>> ctx = tk.context_from_path("/studio.08/demo_project/sequences/AAA/ABC/Lighting/work")
            >>> ctx.as_template_fields(template)
            {'Step': 'Client', 'Shot': 'shot_010', 'Sequence': 'Sequence_1'}

        :param template: Template for which the fields will be used.
        :type  template: tank.TemplatePath.

        :returns: Dictionary of template files representing the context.
                  Handy to pass in to the various Sgtk API methods
        """
        # Get all entities into a dictionary
        entities = {}

        if self.entity:
            entities[self.entity["type"]] = self.entity
        if self.step:
            entities["Step"] = self.step
        if self.task:
            entities["Task"] = self.task
        if self.user:
            entities["HumanUser"] = self.user
        if self.project:
            entities["Project"] = self.project

        # If there are any additional entities, use them as long as they don't
        # conflict with types we already have values for (Step, Task, Shot/Asset/etc)
        for add_entity in self.additional_entities:
            if add_entity["type"] not in entities:
                entities[add_entity["type"]] = add_entity

        fields = {}
        
        # Try to populate fields using paths caches for entity
        if isinstance(template, TemplatePath):
            
            # first, sanity check that we actually have a path cache entry
            # this relates to ticket 22541 where it is possible to create 
            # a context object purely from Shotgun without having it in the path cache
            # (using tk.context_from_entity(Task, 1234) for example)
            #
            # Such a context can result in erronous lookups in the later commands
            # since these make the assumption that the path cache contains the information
            # that is being saught after.
            # 
            # therefore, if the context object contains an entity object and this entity is
            # not represented in the path cache, raise an exception.
            if self.entity and len(self.entity_locations) == 0:
                # context has an entity associated but no path cache entries
                raise TankError("Cannot resolve template data for context '%s' - this context "
                                "does not have any associated folders created on disk yet and "
                                "therefore no template data can be extracted. Please run the folder "
                                "creation for %s and try again!" % (self, self.shotgun_url))
            
            # first look at which ENTITY paths are associated with this context object
            # and use these to extract the right fields for this template
            fields = self._fields_from_entity_paths(template)
            
            # Determine field values by walking down the template tree
            fields.update(self._fields_from_template_tree(template, fields, entities))

        # get values for shotgun query keys in template
        fields.update(self._fields_from_shotgun(template, entities))
        return fields

    def create_copy_for_user(self, user):
        """
        Duplicate the context for the specified 
        user
        
        :param user:    overrides the user
        
        :returns: Context object
        """
        ctx_copy = copy.deepcopy(self)
        ctx_copy.__user = user
        return ctx_copy       

    ################################################################################################
    # private methods

    def _fields_from_shotgun(self, template, entities):
        """
        Query Shotgun server for keys used by this template whose values come directly
        from Shotgun fields.
        """
        fields = {}
        # for any sg query field
        for key in template.keys.values():
            
            # check each key to see if it has shotgun query information that we should resolve
            if key.shotgun_field_name:
                # this key is a shotgun value that needs fetching! 
                
                # ensure that the context actually provides the desired entities
                if not key.shotgun_entity_type in entities:
                    raise TankError("Key '%s' in template '%s' could not be populated by "
                                    "context '%s' because the context does not contain a "
                                    "shotgun entity of type '%s'!" % (key, template, self, key.shotgun_entity_type))
                    
                entity = entities[key.shotgun_entity_type]
                
                # check the context cache 
                cache_key = (entity["type"], entity["id"], key.shotgun_field_name)
                if cache_key in self._entity_fields_cache:
                    # already have the value cached - no need to fetch from shotgun
                    fields[key.name] = self._entity_fields_cache[cache_key]
                
                else:
                    # get the value from shotgun
                    filters = [["id", "is", entity["id"]]]
                    query_fields = [key.shotgun_field_name]
                    result = self.__tk.shotgun.find_one(key.shotgun_entity_type, filters, query_fields)
                    if not result:
                        # no record with that id in shotgun!
                        raise TankError("Could not retrieve Shotgun data for key '%s' in "
                                        "template '%s'. No records in Shotgun are matching "
                                        "entity '%s' (Which is part of the current "
                                        "context '%s')" % (key, template, entity, self))                        

                    value = result.get(key.shotgun_field_name)

                    # note! It is perfectly possible (and may be valid) to return None values from 
                    # shotgun at this point. In these cases, a None field will be returned in the 
                    # fields dictionary from as_template_fields, and this may be injected into
                    # a template with optional fields.
    
                    if value is None:
                        processed_val = None
                    
                    else:

                        # now convert the shotgun value to a string.
                        # note! This means that there is no way currently to create an int key
                        # in a tank template which matches an int field in shotgun, since we are
                        # force converting everything into strings...
                                 
                        processed_val = shotgun_entity.sg_entity_to_string(self.__tk,
                                                                           key.shotgun_entity_type,
                                                                           entity.get("id"),
                                                                           key.shotgun_field_name, 
                                                                           value)
                    
                        if not key.validate(processed_val):                    
                            raise TankError("Template validation failed for value '%s'. This "
                                            "value was retrieved from entity %s in Shotgun to "
                                            "represent key '%s' in "
                                            "template '%s'." % (processed_val, entity, key, template))
                            
                    # all good!
                    # populate dictionary and cache
                    fields[key.name] = processed_val
                    self._entity_fields_cache[cache_key] = processed_val


        return fields


    def _fields_from_entity_paths(self, template):
        """
        Determines template's key values based on context by walking up the context entities paths until
        matches for the template are found.
        """
        fields = {}
        project_roots = self.__tk.pipeline_configuration.get_data_roots().values()

        # get all locations on disk for our context object from the path cache
        path_cache_locations = self.entity_locations 
        
        # now loop over all those locations and check if one of the locations 
        # are matching the template that is passed in. In that case, try to
        # extract the fields values.
        for cur_path in path_cache_locations:
            
            # walk up path until we reach the project root and get values
            while cur_path not in project_roots:
                if template.validate(cur_path):
                    cur_fields = template.get_fields(cur_path)
                    # If there are conflicts, there is ambiguity in the schema
                    for key, value in cur_fields.items():
                        if value != fields.get(key, value):
                            # Value is ambiguous for this key
                            cur_fields[key] = None
                    fields.update(cur_fields)
                    break
                else:
                    cur_path = os.path.dirname(cur_path)
                    
        return fields

    def _fields_from_template_tree(self, template, fields, entities):
        """
        Determines values for a template's keys based on the context by walking down the template tree
        matching template keys with entity types.
        """
        
        # Step 1 - Cull out ambigious templates
        fields = fields.copy()
        for key, value in fields.items():
            if value is None:
                # Note: A none value here indicates an ambiguity 
                # and was set in the _fields_from_entity_paths method.
                del(fields[key])


        # Step 2 - Walk up the template tree and collect templates
        #
        # Use cached paths to find field values
        # these will be returned in top-down order:
        # [<Sgtk TemplatePath sequences/{Sequence}>, 
        #  <Sgtk TemplatePath sequences/{Sequence}/{Shot}>, 
        #  <Sgtk TemplatePath sequences/{Sequence}/{Shot}/{Step}>, 
        #  <Sgtk TemplatePath sequences/{Sequence}/{Shot}/{Step}/publish>, 
        #  <Sgtk TemplatePath sequences/{Sequence}/{Shot}/{Step}/publish/maya>, 
        #  <Sgtk TemplatePath maya_shot_publish: sequences/{Sequence}/{Shot}/{Step}/publish/maya/{name}.v{version}.ma>]
        templates = _get_template_ancestors(template)

        # get a path cache handle
        path_cache = PathCache(self.__tk)

        # Step 3 - walk templates from the root down,
        # for each template, get all paths we have stored in the database
        # and find any fields we can for it
        try:
            # build up a list of fields as we go so that each level matches
            # at least the fields from the previous level
            found_fields = {}

            for cur_template in templates:
                for key in cur_template.keys.values():
                    # If we don't already have a value, look for it
                    if fields.get(key.name) is not None:
                        # already have value so skip:
                        found_fields[key.name] = fields[key.name]
                        continue
                    
                    # only care about entities as this is what we'll look for in the path cache:
                    entity = entities.get(key.name)
                    if entity:
                        # context contains an entity for this Shotgun entity type!
                        temp_fields = _values_from_path_cache(entity, cur_template, path_cache, 
                                                              required_fields=found_fields)
                        # make sure the next iteration finds the same fields: 
                        found_fields.update(temp_fields)
            
            # update the list of fields with all the ones we found:
            fields.update(found_fields)

        finally:    
            path_cache.close()
        
        return fields


################################################################################################
# factory methods for constructing new Context objects, primarily called from the Tank object

def create_empty(tk):
    """
    Constructs an empty context.

    :returns: a context object
    """
    return Context(tk)

def from_entity(tk, entity_type, entity_id):
    """
    Constructs a context from a shotgun entity.
    Because we are constructing the context from an entity, we will get a context
    which has a project, and an entity associated with it.

    If the entity is a Task a call to the Shotgun Server will be made.

    :param tk:           Sgtk API handle
    :param entity_type:  The shotgun entity type to produce a context for
    :param entity_id:    The shotgun entity id to produce a context for

    :returns: a context object
    """
    
    if entity_type is None:
        raise TankError("Cannot create a context from an entity type 'None'!")
    
    if entity_id is None:
        raise TankError("Cannot create a context from an entity id set to 'None'!")
    
    # prep our return data structure
    context = {
        "tk": tk,
        "project": None,
        "entity": None,
        "step": None,
        "user": None,
        "task": None,
        "additional_entities": []
    }

    if entity_type == "Task":
        # For tasks get data from shotgun query
        task_context = _task_from_sg(tk, entity_id)
        context.update(task_context)

    elif entity_type in ["PublishedFile", "TankPublishedFile"]:
        
        sg_entity = tk.shotgun.find_one(entity_type, 
                                        [["id", "is", entity_id]], 
                                        ["project", "entity", "task"])
        
        if sg_entity is None:
            raise TankError("Entity %s with id %s not found in Shotgun!" % (entity_type, entity_id))
        
        if sg_entity.get("task"):
            # base the context on the task for the published file
            return from_entity(tk, "Task", sg_entity["task"]["id"])
        
        elif sg_entity.get("entity"):
            # base the context on the entity that the published is linked with
            return from_entity(tk, sg_entity["entity"]["type"], sg_entity["entity"]["id"])
        
        elif sg_entity.get("project"):
            # base the context on the project that the published is linked with
            return from_entity(tk, "Project", sg_entity["project"]["id"])
    
    else:
        # Get data from path cache
        entity_context = _context_data_from_cache(tk, entity_type, entity_id)
                    
        # make sure this was actually found in the cache
        # fall back on a shotgun lookup if not found
        if entity_context["project"] is None:
            entity_context = _entity_from_sg(tk, entity_type, entity_id)
        
        context.update(entity_context)

    if entity_type == "Project":
        # no need to set entity to point at project in this case
        # that only produces double entries.
        context["entity"] = None

    return Context(**context)

def from_path(tk, path, previous_context=None):
    """
    Constructs a context from a path to a folder or a file.
    The algorithm will navigate upwards in the file system and collect
    as much tank metadata as possible to construct a Tank context.

    Depending on the location, the context contents may vary.

    :param tk:   Sgtk API handle
    :param path: a file system path
    :param previous_context: a context object to use to try to automatically extend the generated
                             context if it is incomplete when extracted from the path. For example,
                             the Task may be carried across from the previous context if it is
                             suitable and if the task wasn't already expressed in the file system
                             path passed in via the path argument.
    :returns: a context object
    """

    # prep our return data structure
    context = {
        "tk": tk,
        "project": None,
        "entity": None,
        "step": None,
        "user": None,
        "task": None,
        "additional_entities": []
    }

    # ask hook for extra entity types we should recognize and insert into the additional_entities list.
    additional_types = tk.execute_core_hook("context_additional_entities").get("entity_types_in_path", [])

    # get a cache handle
    path_cache = PathCache(tk)

    # gather all roots as lower case
    project_roots = [x.lower() for x in tk.pipeline_configuration.get_data_roots().values()]

    # first gather entities
    entities = []
    secondary_entities = []
    curr_path = path
    while True:
        curr_entity = path_cache.get_entity(curr_path)
        if curr_entity:
            # Don't worry about entity types we've already got in the context. In the future
            # we should look for entity ids that conflict in order to flag a degenerate schema.
            entities.append(curr_entity)
        
        # add secondary entities
        secondary_entities.extend( path_cache.get_secondary_entities(curr_path) )

        if curr_path.lower() in project_roots:
            #TODO this could fail with windows path variations
            # we have reached a root!
            break

        # and continue with parent path
        parent_path = os.path.abspath(os.path.join(curr_path, ".."))

        if curr_path == parent_path:
            # We're at the disk root, probably a degenerate path
            break
        else:
            curr_path = parent_path

    path_cache.close()

    # now populate the context
    # go from the root down, so that in the case there are a path with
    # multiple entities (like PROJECT/SEQUENCE/SHOT), the last entry
    # is the most relevant one, and will be assigned as the entity
    for curr_entity in entities[::-1]:
        # handle the special context fields first
        if curr_entity["type"] == "Project":
            context["project"] = curr_entity
        elif curr_entity["type"] == "Step":
            context["step"] = curr_entity
        elif curr_entity["type"] == "Task":
            context["task"] = curr_entity
        elif curr_entity["type"] == "HumanUser":
            context["user"] = curr_entity
        elif curr_entity["type"] in additional_types:
            context["additional_entities"].append(curr_entity)
        else:
            context["entity"] = curr_entity

    # now that the context has been populated as much as possible using the
    # primary entities, fill in any blanks based on the secondary entities.
    for curr_entity in secondary_entities[::-1]:
        # handle the special context fields first
        if curr_entity["type"] == "Project":
            if context["project"] is None:
                context["project"] = curr_entity
        
        elif curr_entity["type"] == "Step":
            if context["step"] is None:
                context["step"] = curr_entity
        
        elif curr_entity["type"] == "Task":
            if context["task"] is None:
                context["task"] = curr_entity
        
        elif curr_entity["type"] == "HumanUser":
            if context["user"] is None:
                context["user"] = curr_entity
        
        elif curr_entity["type"] in additional_types:
            # is this entity in the list already
            if curr_entity not in context["additional_entities"]:            
                context["additional_entities"].append(curr_entity)
        
        else:
            if context["entity"] is None:
                context["entity"] = curr_entity

    # see if we can populate it based on the previous context
    if previous_context and \
       context.get("entity") == previous_context.entity and \
       context.get("additional_entities") == previous_context.additional_entities:

        # cool, everything is matching down to the step/task level.
        # if context is missing a step and a task, we try to auto populate it.
        # (note: weird edge that a context can have a task but no step)
        if context.get("task") is None and context.get("step") is None:
            context["step"] = previous_context.step

        # now try to assign previous task but only if the step matches!
        if context.get("task") is None and context.get("step") == previous_context.step:
            context["task"] = previous_context.task

    # ensure that we don't have a Project as the entity. Projects should only 
    # appear on the projects level, despite being entities.
    if context["project"] and context["entity"] and context["entity"]["type"] == "Project":
        # remove double entry!
        context["entity"] = None

    return Context(**context)

################################################################################################
# serialization

def serialize(context):
    """
    Serializes the context into a string
    """
    from .api import Tank, get_current_user

    data = {
        "project": context.project,
        "entity": context.entity,
        "user": context.user,
        "step": context.step,
        "task": context.task,
        "additional_entities": context.additional_entities,
        "_pc_path": context.tank.pipeline_configuration.get_path()
    }

    # If there is a current user.
    user = get_current_user()
    if user:
        # We should serialize it as well.
        data["current_user"] = user.serialize()
    return pickle.dumps(data)


def deserialize(context_str):
    """
    Deserializes a string created with serialize() into a context object
    """
    # lazy load this to avoid cyclic dependencies
    from .api import Tank, set_current_user
    from tank_vendor import shotgun_authentication as sg_auth
    
    data = pickle.loads(context_str)

    # first get the pc path out of the dict
    pipeline_config_path = data["_pc_path"] 
    del data["_pc_path"]

    # See if there is a current user set.
    user_string = data.get("current_user")
    if user_string:
        # Remove it from the data
        del data["current_user"]
        # and set the current user.
        user = sg_auth.deserialize_user(user_string)
        set_current_user(user)

    # create a Sgtk API instance.
    tk = Tank(pipeline_config_path)

    # add it to the constructor instance
    data["tk"] = tk

    # and lastly make the obejct
    return Context(**data)
    



################################################################################################
# YAML representer/constructor

def context_yaml_representer(dumper, context):
    """
    Custom serializer.
    Creates yaml code for a context object
    """
    
    # first get the stuff which represents all the Context() 
    # constructor parameters
    context_dict = {
        "project": context.project,
        "entity": context.entity,
        "user": context.user,
        "step": context.step,
        "task": context.task,
        "additional_entities": context.additional_entities
    }
    
    # now we also need to pass a TK instance to the constructor when we 
    # are deserializing the object. For this purpose, pass a 
    # PC path as part of the dict
    context_dict["_pc_path"] = context.tank.pipeline_configuration.get_path()

    return dumper.represent_mapping(u'!TankContext', context_dict)

def context_yaml_constructor(loader, node):
    """
    Custom deserializer.
    Constructs a context object given the yaml data provided.
    """
    # lazy load this to avoid cyclic dependencies
    from .api import Tank
    
    # get the dict from yaml
    context_constructor_dict = loader.construct_mapping(node)
    
    # first get the pc path out of the dict
    pipeline_config_path = context_constructor_dict["_pc_path"] 
    del context_constructor_dict["_pc_path"]
    
    # create a Sgtk API instance.
    tk = Tank(pipeline_config_path)

    # add it to the constructor instance
    context_constructor_dict["tk"] = tk

    # and lastly make the obejct
    return Context(**context_constructor_dict)

yaml.add_representer(Context, context_yaml_representer)
yaml.add_constructor(u'!TankContext', context_yaml_constructor)

################################################################################################
# utility methods

def _task_from_sg(tk, task_id):
    """
    Constructs a context from a shotgun task.
    Because we are constructing the context from a task, we will get a context
    which has both a project, an entity a step and a task associated with it.

    Manne 9 April 2013: could we use the path cache primarily and fall back onto
                        a shotgun lookup? 

    :param tk:           a Sgtk API instance
    :param task_id:      The shotgun task id to produce a context for.
    """
    context = {}

    # Look up task's step and entity. This information should be static in practice, so we could
    # likely cache it in the future.

    standard_fields = ["content", "entity", "step", "project"]
    # theses keys map directly to linked entities, users will be handled separately
    context_keys = ["project", "entity", "step", "task"]

    # ask hook for extra Task entity fields we should query and insert into the additional_entities list.
    additional_fields = tk.execute_core_hook("context_additional_entities").get("entity_fields_on_task", [])

    task = tk.shotgun.find_one("Task", [["id","is",task_id]], standard_fields + additional_fields)
    if not task:
        raise TankError("Unable to locate Task with id %s in Shotgun" % task_id)

    # add task so it can be processed with other shotgun entities
    task["task"] = {"type": "Task", "id": task_id, "name": task["content"]}

    for key in context_keys + additional_fields:
        data = task.get(key)
        if data is None:
            # gracefully skip stuff we don't have
            # for example tasks may not have a step
            continue

        # be explicit about what we pull in - make no assumptions about what is
        # being returned from sg (the unit tests mocker doesn't return the same as the API)
        value = {
            "name": data.get("name"),
            "id": data.get("id"),
            "type": data.get("type")
        }

        if key in context_keys:
            context[key] = value
        elif key in additional_fields:
            additional_entities = context.get("additional_entities", [])
            additional_entities.append(value)
            context["additional_entities"] = additional_entities

    return context


def _entity_from_sg(tk, entity_type, entity_id):
    """
    Determines the entity details for the specified entity type and id by querying Shotgun.
                        
    If entity_type is 'Project' then this will return a single dictionary for the project.  For all
    other entity types, this will return dictionaries for both the entity and the project the entity 
    exists under.
                        
    :param tk:          The sgtk api instance
    :param entity_type: The entity type to build a context for
    :param entity_id:   The entity id to build a context for
    :returns:           Dictionary containing either a project entity-dictionary or both
                        project and entity entity-dictionaries depending on the input entity type.
                        e.g. 
                        {
                            "project":{"type":"Project", "id":123, "name":"My Project"},
                            "entity":{"type":"Shot", "id":456, "name":"My Shot"}
                        }
                            
    """

    # deal with funny naming for certain entities 
    if entity_type == "HumanUser":
        # note: previously this would return 'login' but this was inconsistent as the HumanUser
        # entity already has a name field and this could lead to errors later on!
        name_field = "name"
    elif entity_type == "Project":
        name_field = "name"
    else:
        name_field = "code"

    data = tk.shotgun.find_one(entity_type, [["id", "is", entity_id]], ["project", name_field])

    if not data:
        raise TankError("Unable to locate %s with id %s in Shotgun" % (entity_type, entity_id))

    # create context
    context = {}
    
    if entity_type == "Project":
        context["project"] = {"type":"Project", "id": entity_id, "name": data.get(name_field) }
    
    else:
        context["entity"] = {"type": entity_type, "id": entity_id, "name": data.get(name_field) }
        context["project"] = data.get("project")     

    return context


def _context_data_from_cache(tk, entity_type, entity_id):
    """Adds data to context based on path cache.

    :param tk: a Sgtk API instance
    :param entity_type: a Shotgun entity type
    :param entity_id: a Shotgun entity id
    """
    context = {}

    # Set entity info for input entity
    context["entity"] = {"type": entity_type, "id": entity_id}

    # Map entity types to context fields
    types_fields = {"Project": "project",
                    "Step": "step",
                    "Task": "task"}

    # Use the path cache to look up all paths linked to the entity and use that to extract
    # extra entities we should include in the context
    path_cache = PathCache(tk)

    # Grab all project roots
    project_roots = tk.pipeline_configuration.get_data_roots().values()

    # Special case for project as we have the primary data path, which 
    # always points at a project. We only check if the associated configuration
    # has any associated data roots, otherwise a primary config won't exist.
    if tk.pipeline_configuration.has_associated_data_roots():
        context["project"] = path_cache.get_entity(tk.pipeline_configuration.get_primary_data_root())
    else:
        context["project"] = None

    paths = path_cache.get_paths(entity_type, entity_id, primary_only=True)

    for path in paths:
        # now recurse upwards and look for entity types we haven't found yet
        curr_path = path
        curr_entity = path_cache.get_entity(curr_path)
        
        if curr_entity is None:
            # this is some sort of anomaly! the path returned by get_paths
            # does not resolve in get_entity. This can happen if the storage
            # mappings are not consistent or if there is not a 1 to 1 relationship
            #
            # This can also happen if there are extra slashes at the end of the path
            # in the local storage defs and in the pipeline_configuration.yml file.
            raise TankError("The path '%s' associated with %s id %s does not " 
                            "resolve correctly. This may be an indication of an issue "
                            "with the local storage setup. Please contact " 
                            "toolkitsupport@shotgunsoftware.com" % (curr_path, entity_type, entity_id))

        # grab the name for the context entity
        if curr_entity["type"] == entity_type and curr_entity["id"] == entity_id:
            context["entity"]["name"] = curr_entity["name"]

        # note - paths returned by get_paths are always prefixed with a
        # project root so there is no risk we end up with an infinite loop here..
        while curr_path not in project_roots:
            curr_path = os.path.abspath(os.path.join(curr_path, ".."))
            curr_entity = path_cache.get_entity(curr_path)
            if curr_entity:
                cur_type = curr_entity["type"]
                if cur_type in types_fields:
                    field_name = types_fields[cur_type]
                    context[field_name] = curr_entity

    path_cache.close()
    return context


def _values_from_path_cache(entity, cur_template, path_cache, required_fields):
    """
    Determine values for template fields based on an entities cached paths.
                            
    :param entity:          The entity to search for fields for
    :param cur_template:    The template to use to search the path cache
    :path_cache:            An instance of the path_cache to search in
    :param required_fields: A list of fields that must exist in any matched path
    :return:                Dictionary of fields found by matching the template against all paths
                            found for the entity
    """
    
    # use the databsae to go from shotgun type/id --> paths
    entity_paths = path_cache.get_paths(entity["type"], entity["id"], primary_only=True)
    
    # Mapping for field values found in conjunction with this entities paths
    unique_fields = {}
    # keys whose values should be removed from return values
    remove_keys = set()
    
    for path in entity_paths:
        
        # validate path and get fields:
        path_fields = cur_template.validate_and_get_fields(path, required_fields = required_fields)
        if not path_fields:
            continue
        
        # Check values against those found for other paths
        for key, value in path_fields.items():
            if key in unique_fields and value != unique_fields[key]:
                # value for this key isn't unique!
                if key == entity["type"]:
                    # Ambiguity for Entity key
                    # now it is possible that we have ambiguity here, but it is normally
                    # an edge case. For example imagine that an asset has paths
                    # /proj/hero_HIGH
                    # /proj/hero_LOW
                    # and we are mapping against template /%(Project)s/%(Asset)s
                    # both paths are valid matches, so we have ambiguous state for the entity
                    msg = "Ambiguous data. Multiple paths cached for %s which match template %s"
                    raise TankError(msg % (str(entity), str(cur_template)))
                else:
                    # ambiguity for Static key
                    unique_fields[key] = None
                    remove_keys.add(key)
            
            else:
                unique_fields[key] = value
        
    # we want to remove the None/ambiguous values so they don't interfere with other entities
    for remove_key in remove_keys:
        del(unique_fields[remove_key])
    
    return unique_fields


def _get_template_ancestors(template):
    """Return templates branch of the template tree, ordered from first template
    below the project root down to and including the input template.
    """
    # TODO this would probably be better as the Template's responsibility
    templates = [template]
    cur_template = template
    while cur_template.parent is not None and len(cur_template.parent.keys) > 0:
        next_template = cur_template.parent
        templates.insert(0, next_template)
        cur_template = next_template
    return templates
