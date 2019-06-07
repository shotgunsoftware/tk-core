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

        if tk.pipeline_configuration.has_associated_data_roots():
            self._path_cache_disabled = False
            self._roots = tk.pipeline_configuration.get_data_roots()
        else:
            # no primary location found. Path cache therefore does not exist!
            # go into a no-path-cache-mode
            self._path_cache_disabled = True

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
        # Noop. We don't sync anything in an in-memory path cache.

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
                            SG_PATH_FIELD: { "local_path": d["path"], "name": path_display_name }
                            } }

            sg_batch_data.append(req)

        # push to shotgun in a single xact
        log.debug("Uploading %s path entries to Shotgun..." % len(sg_batch_data))

        try:
            response = self._tk.shotgun.batch(sg_batch_data)
        except Exception as e:
            raise TankError("Critical! Could not update Shotgun with folder "
                            "data. Please contact support. Error details: %s" % e)

        # now create a dictionary where input path cache rowid (path_cache_row_id)
        # is mapped to the shotgun ids that were just created
        def _rowid_from_path(path):
            for d in data:
                if d["path"] == path:
                    return d["path_cache_row_id"]
            raise TankError("Could not resolve row id for path! Please contact support! "
                            "trying to resolve path '%s'. Source data set: %s" % (path, data))

        rowid_sgid_lookup = {}
        for sg_obj in response:
            sg_id = sg_obj["id"]
            pc_row_id = _rowid_from_path( sg_obj[SG_PATH_FIELD]["local_path"] )
            rowid_sgid_lookup[pc_row_id] = sg_id

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

        # return the event log id which represents this uploaded slab
        return (response["id"], rowid_sgid_lookup)

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
        raise NotImplementedError("PathCache.validate_mappings")

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
        raise NotImplementedError("PathCache.add_mappings")

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

    def get_paths(self, entity_type, entity_id, primary_only, cursor=None):
        """
        Returns a path given a shotgun entity (type/id pair)

        :param entity_type: A Shotgun entity type
        :param entity_id: A Shotgun entity id
        :param primary_only: Only return items marked as primary
        :param cursor: Database cursor to use. If none, a new cursor will be created.
        :returns: A path on disk
        """
        raise NotImplementedError("PathCache.get_paths")

    def get_entity(self, path, cursor=None):
        """
        Returns an entity given a path.

        If this path is made up of nested entities (e.g. has a folder creation expression
        on the form Shot: "{code}_{sg_sequence.Sequence.code}"), the primary entity (in
        this case the Shot) will be returned.

        Note that if the lookup fails, none is returned.

        :param path: a path on disk
        :param cursor: Database cursor to use. If none, a new cursor will be created.
        :returns: Shotgun entity dict, e.g. {"type": "Shot", "name": "xxx", "id": 123}
                or None if not found
        """
        raise NotImplementedError("PathCache.get_entity")

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
