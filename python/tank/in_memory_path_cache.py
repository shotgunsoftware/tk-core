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
Methods relating to the Path cache, a central repository where metadata about
all Tank items in the file system are kept.

"""

import collections
import sys
import os
import itertools

# use api json to cover py 2.5
# todo - replace with proper external library
from tank_vendor import shotgun_api3
json = shotgun_api3.shotgun.json

from .platform.engine import show_global_busy, clear_global_busy
from . import constants
from .errors import TankError
from . import LogManager
from .util.login import get_current_user
from .util.shotgun_path import ShotgunPath

# Shotgun field definitions to store the path cache data
SHOTGUN_ENTITY = "FilesystemLocation"
SG_ENTITY_FIELD = "entity"
SG_PATH_FIELD = "path"
SG_METADATA_FIELD = "configuration_metadata"
SG_IS_PRIMARY_FIELD = "is_primary"
SG_ENTITY_ID_FIELD = "linked_entity_id"
SG_ENTITY_TYPE_FIELD = "linked_entity_type"
SG_ENTITY_NAME_FIELD = "code"
SG_PIPELINE_CONFIG_FIELD = "pipeline_configuration"

log = LogManager.get_logger(__name__)


class FilesystemLocationEntry(object):

    __slots__ = ["link", "is_primary", "storage", "relative_path"]

    def __init__(self):
        pass


class InMemoryPathCache(object):
    """
    A global cache which holds the mapping between a shotgun entity and a location on disk.
    """

    def __init__(self, tk):
        """
        Constructor.

        :param tk: Toolkit API instance
        """
        self._tk = tk
        self._cache = []

        if tk.pipeline_configuration.has_associated_data_roots():
            self._path_cache_disabled = False
            self._roots = tk.pipeline_configuration.get_data_roots()
        else:
            # no primary location found. Path cache therefore does not exist!
            # go into a no-path-cache-mode
            self._path_cache_disabled = True

    def close(self):
        """
        Close the database connection.
        """
        # Noop. There is no database to close with an in-memory path cache.

    ############################################################################################
    # shotgun synchronization (SG data pushed into path cache database)

    def synchronize(self, full_sync=False):
        """
        Ensure the local path cache is in sync with Shotgun.

        If the method decides to do a full sync, it will attempt to
        launch the busy overlay window.

        :param full_sync: Boolean to indicate that a full sync should be carried out.

        :returns: A list of remote items which were detected, created remotely
                and not existing in this path cache. These are returned as a list of
                dictionaries, each containing keys:
                    - entity
                    - metadata
                    - path
        """
        # Clear the cache we have, we want the latest and greatest from shotgun.
        self._cache = []
        return []

    @classmethod
    def remove_filesystem_location_entries(cls, tk, path_ids):
        """
        Removes FilesystemLocation entries from the path cache.

        :param list path_ids: List of FilesystemLocation ids to remove.
        """
        raise NotImplementedError("PathCache.remove_filesystem_location_entries")

    ############################################################################################
    # pre-insertion validation

    def validate_mappings(self, data):
        """
        Checks a series of path mappings to ensure that they don't conflict with
        existing path cache data.

        :param data: list of dictionaries. Each dictionary should contain
                    the following keys:
                    - entity: a dictionary with keys name, id and type
                    - path: a path on disk
                    - primary: a boolean indicating if this is a primary entry
                    - metadata: configuration metadata
        """
        print("PathCache.validate_mappings not implemented for now.")
        # raise NotImplementedError("PathCache.validate_mappings")

    ############################################################################################
    # database insertion methods

    def add_mappings(self, data, entity_type, entity_ids):
        """
        Adds a collection of mappings to the path cache in case they are not
        already there.

        :param data: list of dictionaries. Each dictionary contains
                    the following keys:
                    - entity: a dictionary with keys name, id and type
                    - path: a path on disk
                    - primary: a boolean indicating if this is a primary entry
                    - metadata: folder configuration metadata

        :param entity_type: sg entity type for the original high level folder creation
                            request that represents this series of mappings
        :param entity_ids: list of sg entity ids (ints) that represents which objects triggered
                        the high level folder creation request.

        """
        # Seems like the code never invokes this with more than one entry.
        assert len(entity_ids) == 1 or len(entity_ids) == 0

        data_for_sg = []

        for d in data:
            if self._has_shotgun_entry(d["path"], d["entity"], d["primary"]) is False:
                data_for_sg.append(d)

        if len(data_for_sg) > 0:
            # first, a summary of what we are up to for the event log description
            entity_ids = ", ".join([str(x) for x in entity_ids])
            desc = ("Created folders on disk for %ss with id: %s" % (entity_type, entity_ids))

            # now push to shotgun
            self._upload_cache_data_to_shotgun(data_for_sg, desc)

    def _has_shotgun_entry(self, path, entity, primary):
        """
        Adds an association to the database. If the association already exists, it will
        do nothing, just return.
        
        If there is another association which conflicts with the association that is 
        to be inserted, a TankError is raised.

        :param path: a path on disk representing the entity.
        :param entity: a shotgun entity dict with keys type, id and name
        :param primary: is this the primary entry for this particular path     
        
        :returns: ``False`` is nothing was 
        """
        # only support primary for now
        assert(primary)

        # the primary entity must be unique: path/id/type
        # see if there are any records for this path
        # note that get_entity does not return secondary entities
        curr_entity = self.get_entity(path)

        if curr_entity is not None:
            # this path is already registered. Ensure it is connected to
            # our entity!
            #
            # Note! We are only comparing against the type and the id
            # not against the name. It should be perfectly valid to rename something
            # in shotgun and if folders are then recreated for that item, nothing happens
            # because there is already a folder which repreents that item. (although now with
            # an incorrect name)
            #
            # also note that we have already done this once as part of the validation checks -
            # this time round, we are doing it more as an integrity check.
            #
            if curr_entity["type"] != entity["type"] or curr_entity["id"] != entity["id"]:
                raise TankError("Database concurrency problems: The path '%s' is "
                                "already associated with Shotgun entity %s. Please re-run "
                                "folder creation to try again." % (path, str(curr_entity) ))

            else:
                # the entry that exists in the db matches what we are trying to insert so skip it
                return True

        return False
        # entities = self._get_mappings_missing_from_sg(data)

    # def _get_mappings_missing_from_sg(self, data):

    #     entities = self._get_entities_from_sg(data)

    #     # Create a fast lookup for the mappings.
    #     entities_per_id = {
    #         entity["id"]: entity for entity in entities
    #     }

    #     data_for_sg = []
    #     for entry in entities:
    #         if entry["id"]

    def _get_entities_from_sg(self, data):
        # Create a predicate that will retrieve all the entities matching a given
        # set of path and their storage.
        any_paths_predicate = {
            "filter_operator": "any",
            "filters": [self._path_to_predicate(d["path"]) for d in data]
        }

        any_primary_paths_predicate = [
            ["is_primary", "is", True],
            any_paths_predicate
        ]

        entities = self._tk.shotgun.find(
            "FilesystemLocation",
            any_primary_paths_predicate,
            [SG_ENTITY_ID_FIELD, SG_ENTITY_TYPE_FIELD, SG_ENTITY_NAME_FIELD]
        )

        return entities

    def _path_to_predicate(self, path):

        root_name, relative_path = self._separate_root(path)
        db_path = self._path_to_dbpath(relative_path)

        return {
            "filter_operator": "all",
            "filters": [
                ["path_cache", "is", db_path],
                ["path_cache_storage", "is", root_name]
            ]
        }


    ############################################################################################
    # database accessor methods

    def get_shotgun_id_from_path(self, path):
        """
        Returns a FilesystemLocation id given a path.

        :param path: Path to look for in the path cache
        :returns: A shotgun FilesystemLocation id or None if not found.
        """
        raise NotImplementedError("PathCache.get_shotgun_id_from_path")

    def get_folder_tree_from_sg_id(self, shotgun_id):
        """
        Returns a list of items making up the subtree below a certain shotgun id
        Each item in the list is a dictionary with keys path and sg_id.

        :param shotgun_id: The shotgun filesystem location id which should be unregistered.
        :returns: A list of items making up the subtree below the given id
        """
        raise NotImplementedError("PathCache.get_folder_tree_from_sg_id")

    def get_paths(self, entity_type, entity_id, primary_only):
        """
        Returns a path given a shotgun entity (type/id pair)

        :param entity_type: A Shotgun entity type
        :param entity_id: A Shotgun entity id
        :param primary_only: Only return items marked as primary
        :returns: A path on disk
        """
        if self._path_cache_disabled:
            # no entries because we don't have a path cache
            return []

        assert primary_only

        entries = self._tk.shotgun.find(
            "FilesystemLocation",
            [
                [SG_ENTITY_ID_FIELD, "is", entity_id],
                [SG_ENTITY_TYPE_FIELD, "is", entity_type],
                ["is_primary", "is", True]
            ],
            ["path_cache", "path_cache_storage"]
        )

        paths = []

        for entry in entries:
            root_name = entry["path_cache_storage"]
            relative_path = entry["path_cache"]

            root_path = self._roots.get(root_name)
            if not root_path:
                # The root name doesn't match a recognized name, so skip this entry
                continue
            
            # assemble path
            path_str = self._dbpath_to_path(root_path, relative_path)
            paths.append(path_str)

        return paths

    def get_entity(self, path):
        """
        Returns an entity given a path.

        If this path is made up of nested entities (e.g. has a folder creation expression
        on the form Shot: "{code}_{sg_sequence.Sequence.code}"), the primary entity (in
        this case the Shot) will be returned.

        Note that if the lookup fails, none is returned.

        :param path: a path on disk
        :returns: Shotgun entity dict, e.g. {"type": "Shot", "name": "xxx", "id": 123}
                or None if not found
        """

        if path is None:
            # basic sanity checking
            import pdb
            pdb.set_trace()
            return None

        entities = self._get_entities_from_sg([{"path": path}])
        if len(entities) > 1:
            # never supposed to happen!
            raise TankError("More than one entry in path database for %s!" % path)
        elif len(entities) == 1:
            # convert to string, not unicode!
            return {
                "type": entities[0][SG_ENTITY_TYPE_FIELD],
                "id": entities[0][SG_ENTITY_ID_FIELD],
                "name": entities[0][SG_ENTITY_NAME_FIELD],
            }
        else:
            return None

    def get_secondary_entities(self, path):
        """
        Returns all the secondary entities for a path.

        :param path: a path on disk
        :returns: list of shotgun entity dicts, e.g. [{"type": "Shot", "name": "xxx", "id": 123}]
                or [] if no entities associated.
        """
        raise NotImplementedError("PathCache.get_secondary_entities")

    def ensure_all_entries_are_in_shotgun(self):
        """
        Ensures that all the path cache data in this database is also registered in Shotgun.

        This will go through each entity in the path cache database and check if it exists in
        Shotgun. If not, it will be created.

        No updates will be made to the path cache database.
        """
        raise NotImplementedError("PathCache.ensure_all_entries_are_in_shotgun")

    def _path_to_dbpath(self, relative_path):
        """
        converts a  relative path to a db path form

        /foo/bar --> /foo/bar
        \foo\bar --> /foo/bar
        """
        # normalize the path before checking the project
        # some tools on windows the / others \

        # normalize
        norm_path = relative_path.replace(os.sep, "/")
        return norm_path

    def _separate_root(self, full_path):
        """
        Determines project root path and relative path.

        :returns: root_name, relative_path
        """
        n_path = full_path.replace(os.sep, "/")
        # Deterimine which root
        root_name = None
        relative_path = None
        for cur_root_name, root_path in self._roots.items():
            n_root = root_path.replace(os.sep, "/")
            if n_path.lower().startswith(n_root.lower()):
                root_name = cur_root_name
                # chop off root
                relative_path = full_path[len(root_path):]
                break

        if not root_name:
            
            storages_str = ",".join( self._roots.values() )
            
            raise TankError("The path '%s' could not be split up into a project centric path for "
                            "any of the storages %s that are associated with this "
                            "project." % (full_path, storages_str))

        return root_name, relative_path


    def _dbpath_to_path(self, root_path, dbpath):
        """
        converts a dbpath to path for the local platform

        linux:    /foo/bar --> /studio/proj/foo/bar
        windows:  /foo/bar --> \\studio\proj\foo\bar         

        :param root_path: Project root path
        :param db_path: Relative path
        """
        # first make sure dbpath doesn't start with a /
        if dbpath.startswith("/"):
            dbpath = dbpath[1:]
        # convert slashes
        path_sep = dbpath.replace("/", os.sep)
        # and join with root
        full_path = os.path.join(root_path, path_sep)
        return os.path.normpath(full_path)

    def _upload_cache_data_to_shotgun(self, data, event_log_desc):
        """
        Takes a standard chunk of Shotgun data and uploads it to Shotgun
        using a single batch statement. Then writes a single event log entry record
        which binds the created path records. Returns the id of this event log record.
        
        data needs to be a list of dicts with the following keys:
        - entity - std sg entity dict with name, id and type
        - primary - boolean to indicate if something is primary
        - metadata - metadata dict
        - path - local os path
        - path_cache_row_id - the path cache db row id for the entry
        
        :param data: List of dicts. See details above.
        :param event_log_desc: Description to add to the event log entry created.
        :returns: A tuple with (event_log_id, sg_id_lookup)
                - event_log_id is the id for the event log entry which summarizes the 
                    creation event.
                - sg_id_lookup is a dictionary where the keys are path cache row ids 
                    and the values are the newly created corresponding shotgun ids. 
        """

        if self._tk.pipeline_configuration.is_unmanaged():
            # no pipeline config for this one
            pc_link = None
        else:
            pc_link = {
                "type": "PipelineConfiguration",
                "id": self._tk.pipeline_configuration.get_shotgun_id()
            }

        sg_batch_data = []
        for d in data:
                            
            # get a name for the clickable url in the path field
            # this will include the name of the storage
            root_name, relative_path = self._separate_root(d["path"])
            db_path = self._path_to_dbpath(relative_path)
            path_display_name = "[%s] %s" % (root_name, db_path) 
            
            req = {"request_type":"create", 
                "entity_type": SHOTGUN_ENTITY, 
                "data": {"project": self._get_project_link(),
                            "created_by": get_current_user(self._tk),
                            SG_ENTITY_FIELD: d["entity"],
                            SG_IS_PRIMARY_FIELD: d["primary"],
                            SG_PIPELINE_CONFIG_FIELD: pc_link,
                            SG_METADATA_FIELD: json.dumps(d["metadata"]),
                            SG_ENTITY_ID_FIELD: d["entity"]["id"],
                            SG_ENTITY_TYPE_FIELD: d["entity"]["type"],
                            SG_ENTITY_NAME_FIELD: d["entity"]["name"],
                            SG_PATH_FIELD: { "local_path": d["path"], "name": path_display_name },
                            "path_cache_storage": root_name,
                            "path_cache": db_path
                            } }
            
            sg_batch_data.append(req)
        
        # push to shotgun in a single xact
        log.debug("Uploading %s path entries to Shotgun..." % len(sg_batch_data))
        
        try:    
            response = self._tk.shotgun.batch(sg_batch_data)
        except Exception as e:
            raise TankError("Critical! Could not update Shotgun with folder "
                            "data. Please contact support. Error details: %s" % e)
        
        # now register the created ids in the event log
        # this will later on be read by the synchronization            
        # now, based on the entities we just created, assemble a metadata chunk that 
        # the sync calls can use later on.        
        meta = {}
        # the api version used is always useful to know
        meta["core_api_version"] = self._tk.version
        # shotgun ids created
        meta["sg_folder_ids"] = [ x["id"] for x in response]
        
        sg_event_data = {}
        sg_event_data["event_type"] = "Toolkit_Folders_Create"
        sg_event_data["description"] = "Toolkit %s: %s" % (self._tk.version, event_log_desc)
        sg_event_data["project"] = self._get_project_link()
        sg_event_data["entity"] = pc_link
        sg_event_data["meta"] = meta
        sg_event_data["user"] = get_current_user(self._tk)
    
        try:
            log.debug("Creating event log entry %s" % sg_event_data)
            response = self._tk.shotgun.create("EventLogEntry", sg_event_data)
        except Exception as e:
            raise TankError("Critical! Could not update Shotgun with folder data event log "
                            "history marker. Please contact support. Error details: %s" % e)            

    def _get_project_link(self):
        """
        Returns the project link dictionary.

        :returns: If we have a site configuration, None will be returned. Otherwise, a dictionary
            with keys "type" and "id" will be returned.
        """
        if self._tk.pipeline_configuration.is_site_configuration():
            return None
        else:
            return {
                "type": "Project",
                "id": self._tk.pipeline_configuration.get_project_id()
            }