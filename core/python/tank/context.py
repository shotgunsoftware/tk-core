"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Management of the current context, e.g. the current shotgun entity/step/task.

"""

import os

from tank_vendor import yaml

import tank
from . import root
from .util import login
from .util import shotgun
from .folder import folder
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

    def __init__(self, tk, project=None, entity=None, step=None, task=None, user=None, additional_entities=[]):
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
        self.__additional_entities = additional_entities
        self._entity_fields_cache = {}

    def __repr__(self):
        args = (self.project,
                self.entity,
                self.step,
                self.task)
        return "<Tank Context: %s %s %s %s>" % args

    def __eq__(self, other):
        if not isinstance(other, Context):
            return False

        equal = True
        equal &= (self.__project == other.__project)
        equal &= (self.__entity == other.__entity)
        equal &= (self.__step == other.__step)
        equal &= (self.__task == other.__task)
        equal &= (self.__user == other.__user)
        equal &= (self.__additional_entities == other.__additional_entities)

        return equal

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
        The shotgun human user, if any, associated with this context. Try to match the local
        login to a HumanUser in Shotgun the first time it is called.
        """
        if self.__user is None:
            user = login.get_shotgun_user(self.__tk.shotgun)
            self.__user = user
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
        A list of disk locations where the entity can be found
        """
        if self.entity is None:
            return []

        paths = self.__tk.paths_from_entity(self.entity["type"], self.entity["id"])

        return paths

    @property
    def tank(self):
        """
        A Tank API instance
        """
        return self.__tk

    ################################################################################################
    # public methods

    def as_template_fields(self, template):
        """
        Returns the context object as a dictionary of template fields.
        This is useful if you want to use a Context object as part of a call to the Tank API.

            >>> import tank
            >>> tk = tank.Tank("/studio.08/demo_project/sequences/AAA/ABC/Lighting/work")
            >>> template = tk.templates['lighting_work']
            >>> ctx = tk.context_from_path("/studio.08/demo_project/sequences/AAA/ABC/Lighting/work")
            >>> ctx.as_template_fields(template)
            {'Step': 'Client', 'Shot': 'shot_010', 'Sequence': 'Sequence_1'}

        :param template: Template for which the fields will be used.
        :type  template: tank.TemplatePath.

        :returns: Dictionary of template files representing the context.
                  Handy to pass in to the various Tank API methods
        """
        fields = {}
        # Get all entities into a dictionary
        entities = {}

        if self.entity:
            entities[self.entity["type"]] = self.entity
        if self.step:
            entities["Step"] = self.step
        if self.task:
            entities["Task"] = self.task
        if self.project:
            entities["Project"] = self.project

        # If there are any additional entities, use them as long as they don't
        # conflict with types we already have values for (Step, Task, Shot/Asset/etc)
        for add_entity in self.additional_entities:
            if add_entity["type"] not in entities:
                entities[add_entity["type"]] = add_entity

        # Try to populate fields using paths caches for entity
        if isinstance(template, TemplatePath):
            fields.update(self._fields_from_entity_paths(template))
            # Determine field values by walking down the template tree
            fields.update(self._fields_from_template_tree(template, fields, entities))

        # get values for shotgun query keys in template
        fields.update(self._fields_from_shotgun(template, entities))
        return fields

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
            # check each key to see if it has shotgun query information
            # shotgun_field_name can only be set if shotgun_entity_type has a value,
            # so we don't need to check for both.
            if key.shotgun_field_name and key.shotgun_entity_type in entities:
                entity = entities[key.shotgun_entity_type]
                # check the context cache 
                cache_key = (entity["type"], entity["id"], key.shotgun_field_name)
                if cache_key in self._entity_fields_cache:
                    value = self._entity_fields_cache[cache_key]
                else:
                    filters = [["id", "is", entity["id"]]]
                    query_fields = [key.shotgun_field_name]
                    result = self.__tk.shotgun.find_one(key.shotgun_entity_type, filters, query_fields)
                    if not result:
                        # We should be able to query any entity in the context
                        msg =  "Query to shotgun for entity %s has failed." % str(entity)
                        msg += "Template: %s" % str(template)
                        msg += "Context: %s" % str(self)
                        raise TankError(msg)

                    value = result.get(key.shotgun_field_name)

                if value is None:
                    msg = "Shotgun returned None as value for field %s.%s" 
                    msg = msg % (key.shotgun_entity_type, key.shotgun_field_name)
                    raise TankError(msg)
                else:
                    processed_val = folder.generate_string_val(self.__tk,
                                                               key.shotgun_entity_type,
                                                               entity.get("id"),
                                                               key.shotgun_field_name, 
                                                               value)
                    if key.validate(processed_val):
                        fields[key.name] = processed_val
                        self._entity_fields_cache[cache_key] = processed_val
                    else:
                        msg = "Shotgun returned invalid value: %s for field %s.%s" 
                        msg = msg % (str(value), key.shotgun_entity_type, key.shotgun_field_name)
                        raise TankError(msg)

        return fields


    def _fields_from_entity_paths(self, template):
        """
        Determines template's key values based on context by walking up the context entities paths until
        matches for the template are found.
        """
        fields = {}
        project_roots = self.__tk.roots.values()

        for cur_path in self.entity_locations:
            # walk up path until match and get value
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
        # Make copy of fields with no None values for filtering
        fields = fields.copy()
        for key, value in fields.items():
            if value is None:
                del(fields[key])


        # Step 2 - Walk up the template tree and collect templates
        templates = _get_template_ancestors(template)

        # Find primary project root
        project_root = root.get_primary_root(template.root_path)
        # Use cached paths to find field values
        path_cache = PathCache(project_root)

        # Step 3 - walk templates from the root down,
        # for each template, get all paths we have stored in the database
        # and get the filename - this will be our field value
        for cur_template in templates:
            for key in cur_template.keys.values():
                # If we don't already have a value, look for it
                if fields.get(key.name) is None:
                    entity = entities.get(key.name)
                    if entity:
                        # context contains an entity for this Shotgun entity type!
                        temp_fields = _values_from_path_cache(entity, cur_template, path_cache, fields)
                        fields.update(temp_fields)

        path_cache.connection.close()
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

    :param tk:           Tank API handle
    :param entity_type:  The shotgun entity type to produce a context for.
    :param entity_id:    The shotgun entity id to produce a context for.

    :returns: a context object
    """
    # prep our return data structure
    context = {
        "tk": tk,
        "project": None,
        "entity": None,
        "step": None,
        "task": None,
        "additional_entities": []
    }

    if entity_type == "Task":
        # For tasks get data from shotgun query
        task_context = _task_from_sg(tk, entity_id)
        context.update(task_context)

    else:
        # Get data from path cache
        entity_context = _context_data_from_cache(tk, entity_type, entity_id)
        context.update(entity_context)

    return Context(**context)

def from_path(tk, path, previous_context=None):
    """
    Constructs a context from a path to a folder or a file.
    The algorithm will navigate upwards in the file system and collect
    as much tank metadata as possible to construct a Tank context.

    Depending on the location, the context contents may vary.

    :param tk:   Tank API handle
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
        "task": None,
        "additional_entities": []
    }

    # ask hook for extra entity types we should recognize and insert into the additional_entities list.
    additional_types = tk.execute_hook("context_additional_entities").get("entity_types_in_path", [])

    # get a cache handle
    path_cache = PathCache(tk.project_path)

    # gather all roots as lower case
    project_roots = [x.lower() for x in tk.roots.values()]

    # first gather entities
    entities = []
    curr_path = path
    while True:
        curr_entity = path_cache.get_entity(curr_path)
        if curr_entity:
            # Don't worry about entity types we've already got in the context. In the future
            # we should look for entity ids that conflict in order to flag a degenerate schema.
            entities.append(curr_entity)

        if curr_path.lower() in project_roots:
            #TODO this could fail with windows path variations
            # we have reached a root!
            break

        # and continue with parent path
        parent_path = os.path.abspath(os.path.join(curr_path, os.pardir))

        if curr_path == parent_path:
            # We're at the disk root, probably a degenerate path
            break
        else:
            curr_path = parent_path

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

    path_cache.connection.close()

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

    return Context(**context)

################################################################################################
# YAML representer/constructor

def context_yaml_representer(dumper, context):
    context_dict = {
        "tank_project_path": context.tank.project_path,
        "project": context.project,
        "entity": context.entity,
        "step": context.step,
        "task": context.task,
        "additional_entities": context.additional_entities
    }

    return dumper.represent_mapping(u'!TankContext', context_dict)

def context_yaml_constructor(loader, node):
    context_dict = loader.construct_mapping(node)
    tk = tank.Tank(context_dict["tank_project_path"])

    del context_dict["tank_project_path"]
    context_dict["tk"] = tk

    return Context(**context_dict)

yaml.add_representer(Context, context_yaml_representer)
yaml.add_constructor(u'!TankContext', context_yaml_constructor)

################################################################################################
# utility methods

def _task_from_sg(tk, task_id):
    """
    Constructs a context from a shotgun task.
    Because we are constructing the context from a task, we will get a context
    which has both a project, an entity a step and a task associated with it.

    :param tk:           a Tank API instance
    :param task_id:      The shotgun task id to produce a context for.
    """
    context = {}

    # Look up task's step and entity. This information should be static in practice, so we could
    # likely cache it in the future.

    standard_fields = ["content", "entity", "step", "project"]
    # theses keys map directly to linked entities, users will be handled separately
    context_keys = ["project", "entity", "step", "task"]

    # ask hook for extra Task entity fields we should query and insert into the additional_entities list.
    additional_fields = tk.execute_hook("context_additional_entities").get("entity_fields_on_task", [])

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


def _context_data_from_cache(tk, entity_type, entity_id):
    """Adds data to context based on path cache.

    :param tk: a Tank API instance
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
    path_cache = PathCache(tk.project_path)

    # Grab all project roots
    project_roots = tk.roots.values()

    # Special case for project as we have the project root
    context["project"] = path_cache.get_entity(tk.project_path)

    paths = path_cache.get_paths(entity_type, entity_id)

    for path in paths:
        # now recurse upwards and look for entity types we haven't found yet
        curr_path = path
        curr_entity = path_cache.get_entity(curr_path)

        # grab the name for the context entity
        if curr_entity["type"] == entity_type and curr_entity["id"] == entity_id:
            context["entity"]["name"] = curr_entity["name"]

        # note - paths returned by get_paths are always prefixed with a
        # project root so there is no risk we end up with an infinite loop here..
        while curr_path not in project_roots:
            curr_path = os.path.abspath(os.path.join(curr_path, os.pardir))
            curr_entity = path_cache.get_entity(curr_path)
            if curr_entity:
                cur_type = curr_entity["type"]
                if cur_type in types_fields:
                    field_name = types_fields[cur_type]
                    context[field_name] = curr_entity

    path_cache.connection.close()
    return context


def _values_from_path_cache(entity, cur_template, path_cache, fields):
    """
    Determine values for templates fields based on an entities cached paths.
    """
    # use the databsae to go from shotgun type/id --> paths
    entity_paths = path_cache.get_paths(entity["type"], entity["id"])
    # get a list of paths that validate against our current template
    matches = [epath for epath in entity_paths if cur_template.validate(epath, fields=fields)]
    # Mapping for field values found in conjunction with this entities paths
    temp_fields = {}
    # keys whose values should be removed from return values
    remove_keys = set()

    for matched_path in matches:
        # Get the filed values for each path
        matched_fields = cur_template.get_fields(matched_path)
        # Check values against those found for other paths
        for m_key, m_value in matched_fields.items():
            if m_key in temp_fields and m_value != temp_fields[m_key]:
                if m_key == entity["type"]:
                    # Ambiguity for Entity key
                    # now it is possible that we have ambiguity here, but it is normally
                    # an edge case. For example imagine that an asset has paths
                    # /proj/hero_HIGH
                    # /proj/hero_LOW
                    # and we are mapping against template /%(Project)s/%(Asset)s
                    # both paths are valid matches, so we have ambiguous state for the entity
                    path_cache.connection.close()
                    msg = "Ambiguous data. Multiple paths cached for %s which match template %s"
                    raise TankError(msg % (str(entity), str(cur_template)))
                else:
                    # ambiguity for Static key
                    temp_fields[m_key] = None
                    remove_keys.add(m_key)
            else:
                temp_fields[m_key] = m_value

    # we want to remove the None values so they don't interfere with other entities
    for remove_key in remove_keys:
        del(temp_fields[remove_key])

    return temp_fields


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
