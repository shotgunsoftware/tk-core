# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

from ..errors import TankError

from . import ShotgunPath
from . import shotgun
from . import yaml_cache

# TODO: add logging

class StorageRoots(object):
    """
    This class provides an interface for a configuration's defined storage
    roots as specified in config/core/roots.yml.

    The class is instantiated by providing the configuration's root folder.
    Methods are provided for accessing information about the configuration's
    storages including the default storages and paths for the current operating
    system.

    The roots.yml file is a reflection of the local storages setup in Shotgun
    at project setup time and may contain anomalies in the path layout
    structure.

    The roots data will be prepended to paths and used for comparison so it is
    critical that the paths are on a correct normalized form once they have been
    loaded into the system.

    Example roots.yml structure::

        work: {
            mac_path: /studio/work,
            windows_path: None,
            linux_path: /studio/work
            default: True,
            local_storage_id': 123
        }
        data: {
            mac_path: /studio/data,
            windows_path: None,
            linux_path: /studio/data
            local_storage_id: 456
        }
    """

    # the name of the fallback, legacy default storage name if one is not
    # defined explicitly in the roots file
    LEGACY_DEFAULT_STORAGE_NAME = "primary"

    # the file path where storage roots are defined in a configuration
    STORAGE_ROOTS_FILE_PATH = os.path.join("core", "roots.yml")

    @classmethod
    def defined(cls, config_folder):
        """
        Returns True if the configuration has a storage roots definition file.
        False otherwise.
        """
        roots_file = os.path.join(config_folder, cls.STORAGE_ROOTS_FILE_PATH)
        return os.path.exists(roots_file)

    def __init__(self, config_folder):
        """
        Initialize the storage roots object.

        :param config_folder: The config folder within the pipeline
            configuration.
        """

        # ---- set some basic data for the object

        # the supplied roots folder, just in case
        self._config_root_folder = config_folder

        # the full path to the roots file for debugging/messages
        self._storage_roots_file = os.path.join(
            self._config_root_folder,
            self.STORAGE_ROOTS_FILE_PATH
        )

        # load the roots file and store the metadata
        self._storage_roots_metadata = _get_storage_roots_metadata(
            self._storage_roots_file)

        # ---- store information about the roots for easy access

        # fields required for SG local storage queries
        local_storage_fields = ["code", "id"]
        local_storage_fields.extend(ShotgunPath.SHOTGUN_PATH_FIELDS)

        # query all local storages from SG so we can store a lookup of roots
        # defined here to SG storages
        sg = shotgun.get_sg_connection()
        sg_storages = sg.find("LocalStorage", [], local_storage_fields)

        # create lookups of storages by name and id for convenience. we'll check
        # against each root's shotgun_storage_id first, falling back to the
        # name if the id mapping field is not defined.
        sg_storages_by_id = {s["id"]: s for s in sg_storages}
        sg_storages_by_name = {s["code"]: s for s in sg_storages}

        # keep a list of storages that could not be mapped to a SG local storage
        self._unmapped_root_names = []

        # build a lookup of storage root name to local storages SG dicts
        self._local_storage_lookup = {}

        # build a lookup of storage root name to shotgun paths
        self._shotgun_paths_lookup = {}

        self._default_storage_name = None

        # now check that each storage is defined in Shotgun
        for root_name, root_info in self._storage_roots_metadata.iteritems():

            # store a shotgun path for each root definition. sanitize path data
            # by passing it through the ShotgunPath object
            self._shotgun_paths_lookup[root_name] = \
                ShotgunPath.from_shotgun_dict(root_info)

            # check to see if this root is marked as the default
            if root_info.get("default", False):
                self._default_storage_name = root_name

            # see if the shotgun storage id is specified explicitly in the
            # roots.yml file.
            root_storage_id = root_info.get("shotgun_storage_id")
            if root_storage_id and root_storage_id in sg_storages_by_id:
                # found a match. store it in the lookup
                self._local_storage_lookup[root_name] = \
                    sg_storages_by_id[root_storage_id]
                continue

            # if we're here, no storage is specified explicitly. fall back to
            # the storage name.
            if root_name in sg_storages_by_name:
                # found a match. store it in the lookup
                self._local_storage_lookup[root_name] = \
                    sg_storages_by_name[root_name]
                continue

            # if we're here, then we could not map the storage root to a local
            # storage in SG. keep a record of it to report below
            self._unmapped_root_names.append(root_name)

        # no storage root defined explicitly
        if not self._default_storage_name:

            # if there is only one, then that is the default
            if len(self._storage_roots_metadata) == 1:
                self._default_storage_name = \
                    self._storage_roots_metadata.keys()[0]
            else:
                # fall back to the legacy primary storage name
                self._default_storage_name = self._storage_roots_metadata.get(
                    self.LEGACY_DEFAULT_STORAGE_NAME)

            # NOTE: the default storage may still be None

    @property
    def as_shotgun_paths(self):
        """
        A dictionary mapping of storage root names to ShotgunPath objects

        :returns: A dictionary structure with an entry for each storage defined.
            The value of each is a ShotgunPath object for the storage's path
            on disk.

        Example return dictionary::

            {
                "primary"  : <ShotgunPath>,
                "textures" : <ShotgunPath>
            }
        """
        return self._shotgun_paths_lookup

    @property
    def default_path(self):
        """
        A ShotgunPath object for the configuration's default storage root
        """
        if self._default_storage_name not in self._shotgun_paths_lookup:
            # no default storage defined
            return None

        return self._shotgun_paths_lookup[self._default_storage_name]

    @property
    def roots_file(self):
        """
        The path to the storage root file represented by this object.
        """
        return self._storage_roots_file

    @property
    def names(self):
        """
        A list of all storage names required by this configuration.
        """
        return self._storage_roots_metadata.keys()

    @property
    def unmapped(self):
        """
        A list of storage root names defined that can not be mapped to local
        storage entries in Shotgun.

        :return: A list of storage root names.
        """
        return self._unmapped_root_names

    def get_local_storage(self, root_name):
        """
        Returns the corresponding SG local storage for a given storage root
        name.
        :return:
        """
        return self._local_storage_lookup.get(root_name)

    def update(self):
        """
        Updates the storage roots defined by the sourced configuration to
        include the local storage paths as defined in SG. This action will
        overwrite the existing storage roots file for the configuration.
        :return:
        """

        # TODO:
        # build up a new metadata dict
        # iterate over each storage defined and pull the paths from the SG dict
            storage_path = ShotgunPath.from_shotgun_dict(storage_by_name[storage_name])
            roots_data[storage_name] = storage_path.as_shotgun_dict()

        # write the new metadata to disk
        with self._open_auto_created_yml(roots_file) as fh:
            yaml.safe_dump(roots_data, fh)
            fh.write("\n")
            fh.write("# End of file.\n")


def _get_storage_roots_metadata(storage_roots_file):
    """
    Parse the supplied storage roots file

    :param storage_roots_file: Path to the roots file.

    :return: The parsed metadata as a dictionary.
    """

    try:
        # keep a handle on the raw metadata read from the roots file
        metadata = yaml_cache.g_yaml_cache.get(
            storage_roots_file,
            deepcopy_data=False
        ) or {}  # if file is empty, initialize with empty dict
    except Exception as e:
        raise TankError(
            "Looks like the roots file is corrupt or missing. "
            "Please contact support! "
            "File: '%s'. "
            "Error: %s" % (storage_roots_file, e)
        )

    return metadata

# TODO:
@filesystem.with_cleared_umask
def _open_auto_created_yml(path):
    """
    Open a standard auto generated yml for writing.

    - any existing files will be removed
    - the given path will be open for writing in text mode
    - a standard header will be added

    :param path: path to yml file to open for writing
    :return: file handle. It's the respoponsibility of the caller to close this.
    """
    log.debug("Creating auto-generated config file %s" % path)
    # clean out any existing file and replace it with a new one.
    filesystem.safe_delete_file(path)

    # open file for writing
    fh = open(path, "wt")

    fh.write("# This file was auto generated by the Shotgun Pipeline Toolkit.\n")
    fh.write("# Please do not modify by hand as it may be overwritten at any point.\n")
    fh.write("# Created %s\n" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    fh.write("# \n")

    return fh