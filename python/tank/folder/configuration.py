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
Handles the creation of a configuration object structure based on the folder configuration on disk.

"""

import os
import fnmatch

from pprint import pformat

from tank_vendor import inflect

from .folder_types import Static, ListField, Entity, Project, UserWorkspace, ShotgunStep, ShotgunTask

from .. import LogManager

from ..errors import TankError, TankUnreadableFileError
from ..util import yaml_cache
from ..util import LocalStorageRoot, NavChainRoot

log = LogManager.get_logger(__name__)

def read_ignore_files(schema_config_path):
    """
    Reads ignore_files from root of schema if it exists.
    Returns a list of patterns to ignore.
    """
    ignore_files = []
    file_path = os.path.join(schema_config_path, "ignore_files")
    if os.path.exists(file_path):
        open_file = open(file_path, "r")
        try:
            for line in open_file.readlines():
                # skip comments
                if "#" in line:
                    line = line[:line.index("#")]
                line = line.strip()
                if line:
                    ignore_files.append(line)
        finally:
            open_file.close()
    return ignore_files

class FolderConfiguration(object):
    """
    Class that loads the schema from disk and constructs folder objects.
    """

    def __init__(self, tk, schema_config_path):
        """
        Constructor
        """
        self._tk = tk

        # access shotgun nodes by their entity_type
        self._entity_nodes_by_type = {}

        # maintain a list of all Step nodes for special introspection
        self._step_fields = []

        # read skip files config
        self._ignore_files = read_ignore_files(schema_config_path)

        # load schema if we have a LocalStorageRoot root
        roots_by_type = self._tk.pipeline_configuration.get_storage_roots_by_type()
        root_types = roots_by_type.keys()
        if LocalStorageRoot.TYPE in root_types:
            self._load_schema(schema_config_path)

        # load navchains if we have a NavChainRoot root
        if NavChainRoot.TYPE in root_types:
            self._load_navchains(roots_by_type[NavChainRoot.TYPE])


    ##########################################################################################
    # public methods

    def get_folder_objs_for_entity_type(self, entity_type):
        """
        Returns all the nodes representing a particular sg entity type
        """
        return self._entity_nodes_by_type.get(entity_type, [])

    def get_task_step_nodes(self):
        """
        Returns all step nodes in the configuration
        """
        return self._step_fields

    ####################################################################################
    # utility methods

    def _get_sub_directories(self, parent_path):
        """
        Returns all the directories for a given path
        """
        directory_paths = []
        for file_name in os.listdir(parent_path):
            
            # check our ignore list
            if any(fnmatch.fnmatch(file_name, p) for p in self._ignore_files):
                continue
            
            full_path = os.path.join(parent_path, file_name)
            if os.path.isdir(full_path):
                directory_paths.append(full_path)
                
        return directory_paths

    def _get_files_in_folder(self, parent_path):
        """
        Returns all the files for a given path except yml files
        Also ignores any files mentioned in the ignore files list
        """
        file_paths = []
        items_in_folder = os.listdir(parent_path)

        folders = [f for f in items_in_folder if os.path.isdir(os.path.join(parent_path, f))]

        for file_name in items_in_folder:

            full_path = os.path.join(parent_path, file_name)

            if not os.path.isfile(full_path):
                # not a file path!
                continue

            if any(fnmatch.fnmatch(file_name, p) for p in self._ignore_files):
                # don't process files matching ignore pattern(s)
                continue

            if file_name.endswith(".yml") and os.path.splitext(file_name)[0] in folders:
                # this is a foo.yml and we have a folder called foo
                # this means that this is a config file!
                continue
            
            if file_name.endswith("symlink.yml"):
                # this is symlink schema component and not a normal file, so 
                # don't include it in the files enumeration
                continue

            # by now should be left with regular non-system files only
            file_paths.append(full_path)

        return file_paths

    def _get_symlinks_in_folder(self, parent_path):
        """
        Returns all xxx.symlink.yml files in a location.
        
        :param parent_path: file system folder to scan
        :returns: list of (name, target_expression, full_metadata) where name is the name of the symlink 
                  and target_expression is a target expression to be passed into the folder creation. 
                  For example, if the file in the schema location is called "foo_bar.symlink.yml", 
                  the name parameter will be 'foo_bar'. 
        """
        SYMLINK_SUFFIX = ".symlink.yml"
        
        data = []
        
        items_in_folder = os.listdir(parent_path)
        symlinks = [f for f in items_in_folder if f.endswith(SYMLINK_SUFFIX) ]

        for file_name in symlinks:

            full_path = os.path.join(parent_path, file_name)

            try:
                metadata = yaml_cache.g_yaml_cache.get(full_path, deepcopy_data=False) or {}
            except Exception as error:
                raise TankError("Cannot load config file '%s'. Error: %s" % (full_path, error))

            if "target" not in metadata:
                raise TankError("Did not find required 'target' parameter in "
                                "symlink definition file '%s'" % full_path) 
            
            target_expression = metadata["target"]

            symlink_name = file_name[:-len(SYMLINK_SUFFIX)]

            # this is a file path and it
            data.append( (symlink_name, target_expression, metadata) )

        return data


    def _read_metadata(self, full_path):
        """
        Reads metadata file.

        :param full_path: Absolute path without extension
        :returns: Dictionary of file contents or None
        """
        metadata = None
        # check if there is a yml file with the same name
        yml_file = "%s.yml" % full_path
        try:
            metadata = yaml_cache.g_yaml_cache.get(yml_file, deepcopy_data=False)
        except TankUnreadableFileError:
            pass
        except Exception as error:
            raise TankError("Cannot load config file '%s'. Error: %s" % (yml_file, error))

        return metadata

    ##########################################################################################
    # internal stuff


    def _load_schema(self, schema_config_path):
        """
        Scan the config and build objects structure
        """

        project_folders = self._get_sub_directories(schema_config_path)

        # make some space in our obj/entity type mapping
        self._entity_nodes_by_type["Project"] = []

        for project_folder in project_folders:

            # read metadata to determine root path
            metadata = self._read_metadata(project_folder)

            if metadata is None:
                if os.path.basename(project_folder) == "project":

                    # get the default root name from the config
                    default_root = self._tk.pipeline_configuration.get_primary_data_root_name()

                    if not default_root:
                        raise TankError(
                            "Unable to identify a default storage root to use "
                            "while loading the project schema. Check your "
                            "config's roots.yml file to ensure at least one "
                            "storage root is defined. You can specify the "
                            "default root by adding a `default: true` "
                            "key/value to a root's definition."
                        )

                    metadata = {"type": "project", "root_name": default_root}
                else:
                    raise TankError("Project directory missing required yml file: %s.yml" % project_folder)

            if metadata.get("type") != "project":
                raise TankError("Only items of type 'project' are allowed at the root level: %s" % project_folder)

            project_obj = Project.create(self._tk, project_folder, metadata)

            # store it in our lookup tables
            self._entity_nodes_by_type["Project"].append(project_obj)

            # recursively process the rest
            self._process_config_r(project_obj, project_folder)


    def _process_config_r(self, parent_node, parent_path):
        """
        Recursively scan the file system and construct an object
        hierarchy.

        Factory method for Folder objects.
        """
        for full_path in self._get_sub_directories(parent_path):
            # check for metadata (non-static folder)
            metadata = self._read_metadata(full_path)
            if metadata:
                node_type = metadata.get("type", "undefined")

                if node_type == "shotgun_entity":
                    cur_node = Entity.create(self._tk, parent_node, full_path, metadata)

                    # put it into our list where we group entity nodes by entity type
                    et = cur_node.get_entity_type()
                    if et not in self._entity_nodes_by_type:
                        self._entity_nodes_by_type[et] = []
                    self._entity_nodes_by_type[et].append(cur_node)

                elif node_type == "shotgun_list_field":
                    cur_node = ListField.create(self._tk, parent_node, full_path, metadata)

                elif node_type == "static":
                    cur_node = Static.create(self._tk, parent_node, full_path, metadata)

                elif node_type == "user_workspace":
                    cur_node = UserWorkspace.create(self._tk, parent_node, full_path, metadata)

                elif node_type == "shotgun_step":
                    cur_node = ShotgunStep.create(self._tk, parent_node, full_path, metadata)
                    self._step_fields.append(cur_node)

                elif node_type == "shotgun_task":
                    cur_node = ShotgunTask.create(self._tk, parent_node, full_path, metadata)

                else:
                    # don't know this metadata
                    raise TankError("Error in %s. Unknown metadata type '%s'" % (full_path, node_type))
            else:
                # no metadata - so this is just a static folder!
                # specify the type in the metadata chunk for completeness
                # since we are passing this into the hook later
                cur_node = Static.create(self._tk, parent_node, full_path, {"type": "static"})

            # and process children
            self._process_config_r(cur_node, full_path)

        # process symlinks
        for (path, target, metadata) in self._get_symlinks_in_folder(parent_path):
            parent_node.add_symlink(path, target, metadata)


        # now process all files and add them to the parent_node token
        for f in self._get_files_in_folder(parent_path):
            parent_node.add_file(f)


    def _load_navchains(self, roots):
        """
        Load up the hierarchies associated with the current project

        example navchain:
             "navchains": {
                "CustomEntity01": "__flat__",
                "Cut": "Cut.entity",
                "CutItem": "CutItem.cut.entity",
                "Sequence": "Sequence.sg_episode",
                "Shot": "Shot.sg_sequence,Sequence.sg_episode"
            }
        """

        # pull the navchain information for this project
        project_id = self._tk.pipeline_configuration.get_project_id()
        if project_id is None:
            raise ValueError("Cannot load navchains unless the current pipeline"
                " configuration is associated with a project")

        sg_projects = self._tk.shotgun.find("Project", [["id", "is", project_id]], ["tracking_settings"])
        if (len(sg_projects)) == 0:
            raise ValueError("Could not load navchains for project %s" % project_id)
        sg_project = sg_projects[0]
        navchains = sg_project["tracking_settings"]["navchains"]
        log.debug("Processing navchains for project %d: %s" % (project_id, sg_project))

        # pull the schema information we will need to turn the navchain into folder nodes
        sg_entity_schema = self._tk.shotgun.schema_entity_read({"type": "Project", "id": project_id})
        sg_schema = self._tk.shotgun.schema_read({"type": "Project", "id": project_id})
        taskable_entity_types = sg_schema["Task"]["entity"]["properties"]["valid_types"]["value"]

        # Get ready to pluralize
        inflect_engine = inflect.inflect_module.engine()

        # node chains
        # start turning each navchain into a chain of nodes that will capture the appropriate parenting information
        # keep track of them with a mapping from "entity_type:field" to the chain of nodes that are parents of that field
        node_chains = {}
        navchain_items = list(navchains.items())
        while navchain_items:
            entity_type, navchain = navchain_items.pop(0)

            node_chain = []
            navlinks = [link.strip() for link in navchain.split(",")]
            first_link, _, ancestor_chain = navchain.partition(",")

            # all navchains lead to an entity. if the entity can have tasks, we will add a task level
            if entity_type in taskable_entity_types:
                node_chain.insert(0, {"type": "task"})

            # add the entity itself
            entity_dict = {"type": "entity", "entity_type": entity_type}
            node_chain.insert(0, entity_dict)

            # now create the grouping node (directory with the plural form of the node)
            # this is complicated by the fact that we want to group above any categorization
            # of an entity via a list field
            if first_link != "__flat__":
                (parent_entity, parent_field) = first_link.split(".")[0:2]
                sg_parent_field = sg_schema[parent_entity][parent_field]
                parent_field_data_type = sg_parent_field["data_type"]["value"]
                if parent_field_data_type == "list":
                    # create the level for the list values before creating the grouping
                    node_chain.insert(0, {"type": "list", "entity_type": parent_entity, "field": parent_field})

                    # list field processed, so remove it from consideration for further hierarchy
                    first_link, _, ancestor_chain = ancestor_chain.partition(",")
                    if not first_link:
                        first_link = "__flat__"

            # now create the grouping node
            entity_display_name = sg_entity_schema[entity_type]["name"]["value"]
            plural_display_name = inflect_engine.plural(entity_display_name.lower()).capitalize()
            node_chain.insert(0, {"type": "static", "value": plural_display_name})

            # we only care one level up each time through, but either verify that the
            # hierarchy above our parent matches what is specified in other navchains,
            # or add it as a new navchain
            if ancestor_chain:
                ancestor_entity_type = ancestor_chain.partition(".")[0]
                if ancestor_entity_type in navchains:
                    # validate that we don't have incompatible navchains
                    if ancestor_chain != navchains[ancestor_entity_type]:
                        raise ValueError(
                            "Incompatible hierarchies specfied on two different navchains:\n"
                            "  %s: %s\n"
                            "  %s: %s" % \
                            (ancestor_entity_type, navchains[ancestor_entity_type], entity_type, navchain)
                        )
                else:
                    # we don't have this entity type yet, add it
                    navchain_items.append((ancestor_entity_type, ancestor_chain))

            # We are at the end of the chain, figure out where we should be attaching this chain to
            if first_link == "__flat__":
                attach_to = ["Project"]
                attach_via = "project"
            else:
                try:
                    (parent_entity, parent_field) = first_link.split(".")[0:2]
                except ValueError:
                    raise ValueError("Could not parse link into entity and field: '%s' (%s)" % (first_link, navchain))

                sg_parent_field = sg_schema[parent_entity][parent_field]
                parent_field_data_type = sg_parent_field["data_type"]["value"]

                if parent_field_data_type != "entity":
                    raise ValueError("Cannot support any hierarchy that does not end with "
                        "an entity field: %s %s" % (entity_type, navchain))

                attach_to = sg_parent_field["properties"]["valid_types"]["value"]
                attach_via = parent_field

            node_chains[entity_type] = {"chain": node_chain, "attach_to": attach_to, "attach_via": attach_via}
        # while node_chain_items

        # now need to make sure that any entities that we attach to that aren't explicitly
        # in the hierarchy get attached to the root
        for attachment_list in [value["attach_to"] for value in node_chains.values()]:
            for attachment_type in attachment_list:
                # see if we have the new entity type
                if attachment_type != "Project" and attachment_type  not in node_chains:
                    # we will have a grouping node, then the entity node, and then tasks if taskable
                    entity_display_name = sg_entity_schema[attachment_type]["name"]["value"]
                    type_display_name_plural = inflect_engine.plural(entity_display_name.lower()).capitalize()
                    chain = [
                        {"type": "static", "value": type_display_name_plural},
                        {"type": "entity", "entity_type": attachment_type}
                    ]
                    if attachment_type in taskable_entity_types:
                        chain.append({"type": "task"})

                    # add the entities at the root level
                    node_chains[attachment_type] = {
                        "attach_to": ["Project"],
                        "attach_via": "project",
                        "chain": chain
                    }

        # keep track of extra node info
        node_metadata = {}

        # create a project hierarchy per navchain root
        for root in roots:
            # start with the node for the project itself
            root_path = os.path.join("/fake/root", root, "Project")
            project_obj = Project.create(self._tk, root_path, {"type": "project", "root_name": root})
            self._entity_nodes_by_type.setdefault("Project", []).append(project_obj)
            node_metadata[id(project_obj)] = { "node_path": root_path, }
            log.debug("navchain: added Project at '%s'" % root_path)

            # Turn the chains into a nodes
            node_chain_items = list(node_chains.items())
            while node_chain_items:
                # keep track of whether we processed anything
                # if we go through a loop and couldn't find anything with all the dependencies
                # fulfilled that means that we've detected a loop in the configured hierarchy
                processed_item = False

                # entity filtering starts with the project

                for (index, (entity_type, chain)) in enumerate(node_chain_items):
                    # see if we have processed all of the dependencies for this chain
                    if all(item in self._entity_nodes_by_type for item in chain["attach_to"]):
                        for attachment_type in chain["attach_to"]:
                            for attachment_obj in self._entity_nodes_by_type[attachment_type]:
                                parent_obj = attachment_obj

                                # add filters to make sure that all filterable nodes below this one have the correct value in the link field
                                current_filters = [{"path": chain["attach_via"], "relation": "is", "values": ["$%s" % attachment_type]}]

                                for link in chain["chain"]:
                                    if link["type"] == "static":
                                        # static node get it's name for the last element of the path
                                        node_path = os.path.join(node_metadata[id(parent_obj)]["node_path"], link["value"])
                                        static_node = Static.create(self._tk, parent_obj, node_path, {"type": "static"})
                                        node_metadata[id(static_node)] = { "node_path": node_path, }
                                        log.debug("navchain: added static folder at '%s'" % node_path)
                                        parent_obj = static_node
                                    elif link["type"] == "entity":
                                        # not all entities use "code" as their main name
                                        fields_to_try = ["code", "title", "content"]
                                        name_field = None
                                        for field_to_try in fields_to_try:
                                            if field_to_try in sg_schema[link["entity_type"]]:
                                                name_field = field_to_try
                                                break
                                        if name_field is None:
                                            raise ValueError("Unable to figure out the name field for "
                                                "entity type %s in navchain hiearchy" % link["entity_type"])

                                        # apply the current set of filters to restrict which entities we allow to be
                                        # created here
                                        metadata = {
                                            "name": name_field,
                                            "entity_type": link["entity_type"],
                                            "filters": current_filters
                                        }
                                        node_path = os.path.join(node_metadata[id(parent_obj)]["node_path"], link["entity_type"])
                                        entity_node = Entity.create(self._tk, parent_obj, node_path, metadata)

                                        node_metadata[id(entity_node)] = { "node_path": node_path, }
                                        log.debug("navchain: added entity folder at '%s'" % node_path)
                                        log.debug("     filters: %s" % current_filters)
                                        parent_obj = entity_node
                                        self._entity_nodes_by_type.setdefault(link["entity_type"], []).append(entity_node)
                                    elif link["type"] == "list":
                                        metadata = {
                                            "entity_type": link["entity_type"],
                                            "field_name": link["field"],
                                        }
                                        node_path = os.path.join(node_metadata[id(parent_obj)]["node_path"], link["field"])
                                        list_node = ListField.create(self._tk, parent_obj, node_path, metadata)

                                        # need to now limit to matches on this list field
                                        current_filters = current_filters + \
                                            [{"path": link["field"], "relation": "is", "values": ["$%s" % link["field"]]}]
                                        node_metadata[id(list_node)] = { "node_path": node_path, }
                                        log.debug("navchain: added list folder at '%s'" % node_path)
                                        parent_obj = list_node
                                    elif link["type"] == "task":
                                        metadata = {"name": "content"}
                                        node_path = os.path.join(node_metadata[id(parent_obj)]["node_path"], "task")
                                        task_node = ShotgunTask.create(self._tk, parent_obj, node_path, metadata)
                                        node_metadata[id(task_node)] = { "node_path": node_path, }
                                        log.debug("navchain: added task folder at '%s'" % node_path)
                                        parent_obj = task_node
                                    else:
                                        raise ValueError("Unknown link type: %s: %s" % (link["type"], chain))

                        processed_item = True
                        node_chain_items.pop(index)

                if not processed_item:
                    remaining_types = [entity_type for (entity_type, _) in node_chain_items]
                    msg = "Loop detected in the following navchains:\n"
                    msg += "\n".join(["  %s %s" % (entity_type, navchains[entity_type]) for entity_type in remaining_types])
                    raise ValueError(msg)
            # while node_chain_items
        # for root in roots


