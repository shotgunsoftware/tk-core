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
