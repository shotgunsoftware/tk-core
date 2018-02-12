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

from tank_vendor import yaml

from .. import LogManager
from ..errors import TankError

from . import filesystem
from . import ShotgunPath
from . import yaml_cache

log = LogManager.get_logger(__name__)


# TODO:
  # double check:
    # docstring contents
    # params
    # return values
    # logging
  # write:
    # __str__
    # __repr__
    # unit tests

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
    """

    ############################################################################
    # class data

    # the name of the fallback, legacy default storage name if one is not
    # defined explicitly in the roots file
    LEGACY_DEFAULT_STORAGE_NAME = "primary"

    # the file path where storage roots are defined in a configuration
    STORAGE_ROOTS_FILE_PATH = os.path.join("core", "roots.yml")

    # sys.platform-specific path keys as expected in the root definitions
    PLATFORM_KEYS = ["mac_path", "linux_path", "windows_path"]

    ############################################################################
    # class methods

    @classmethod
    def defined(cls, config_folder):
        """
        Returns True if the configuration has a storage roots definition file.
        False otherwise.
        """
        roots_file = os.path.join(config_folder, cls.STORAGE_ROOTS_FILE_PATH)
        return os.path.exists(roots_file)

    @classmethod
    def from_config(cls, config_folder):
        """
        Constructs a StorageRoots object from the supplied config folder.

        :param config_folder: The path to a config folder
        :returns: A StorageRoots instance
        """

        storage_roots = cls()
        storage_roots._init_from_config(config_folder)

        return storage_roots

    @classmethod
    def from_metadata(cls, metadata):
        """
        Constructs a StorageRoots object from the supplied metadata.

        :param metadata: The storage roots metadata this object wraps
        :returns: A StorageRoots instance
        """

        storage_roots = cls()
        storage_roots._process_metadata(metadata)

        return storage_roots

    @classmethod
    def write(cls, sg_connection, config_folder, storage_roots):
        """
        Given a StorageRoots object, write it's contents to the standard roots
        location within the supplied config folder. The method will write the
        corresponding local storage paths to the file as defined in Shotgun.
        This action will overwrite the existing storage roots file for the
        configuration.
        """

        (local_storage_lookup, unmapped_roots) = \
            storage_roots.get_local_storages(sg_connection)

        roots_file = os.path.join(config_folder, cls.STORAGE_ROOTS_FILE_PATH)

        # raise an error if there are any roots that can not be mapped to SG
        # local storage entries
        if unmapped_roots:
            raise TankError(
                "The following storages are defined by %s but is can not be "
                "mapped to a local storage in Shotgun: %s" % (
                    roots_file,
                    ", ".join(unmapped_roots)
                )
            )

        if os.path.exists(roots_file):
            # warn if this file already exists
            log.warning(
                "The file '%s' exists in the configuration "
                "but will be overwritten with an auto generated file." %
                (roots_file,)
            )

        # build up a new metadata dict
        roots_metadata = storage_roots.metadata

        for root_name, root_info in storage_roots:

            # get the cached SG storage dict
            sg_local_storage = local_storage_lookup[root_name]

            # get the local storage as a ShotgunPath object
            storage_sg_path = ShotgunPath.from_shotgun_dict(sg_local_storage)

            # update the root's metadata with the dictionary of all
            # sys.platform-style paths
            root_info.update(storage_sg_path.as_shotgun_dict())

        # write the new metadata to disk
        with filesystem.auto_created_yml(roots_file) as fh:
            yaml.safe_dump(roots_metadata, fh)

    ############################################################################
    # special methods

    def __init__(self):
        """
        Initialize the storage roots object.

        Instances should not be created directly. Use the from_* class methods
        to create storage root instances.

        :param config_folder: The config folder within the pipeline
            configuration.
        """

        # information stored on the object

        # the path to the config folder
        self._config_root_folder = None

        # the path to the roots file
        self._storage_roots_file = None

        # the underlying metadata for the required storage roots
        self._storage_roots_metadata = {}

        # a lookup of storage root names to shotgun paths
        self._shotgun_paths_lookup = {}

        # the default storage name as determined when parsing the metadata
        self._default_storage_name = None

    def __iter__(self):
        """
        Allows iteration over each defined root name and corresponding metadata.
        :return:
        """
        for root_name, root_info in self._storage_roots_metadata.iteritems():
            yield root_name, root_info

    ############################################################################
    # properties

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
    def default(self):
        """
        The name of the default storage root
        """
        return self._default_storage_name

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
    def metadata(self):
        """
        The required storage roots metadata dictionary.

        This is a dictionary representation of the contents of the file.
        :return:
        """
        return self._storage_roots_metadata

    @property
    def roots_file(self):
        """
        The path to the storage root file represented by this object.
        """
        if not self._storage_roots_file:
            return None

        return self._storage_roots_file

    @property
    def required(self):
        """
        A list of all reqired storage root names by this configuration.
        """
        return self._storage_roots_metadata.keys()

    ############################################################################
    # public methods

    def get_local_storages(self, sg_connection):
        """
        Returns a tuple of information about the required storage roots and how
        they map to local storages in SG.

        The first item in the tuple is a dictionary of storage root names mapped
        to a corresponding dictionary of fields for a local storage defined in
        Shotgun.

        The second item is a list of storage roots required by the configuration
        that can not be mapped to a SG local storage.

        Example return value::

            (
                {
                    "work": {
                        "code": "primary",
                        "type": "LocalStorage",
                        "id": 123
                        "linux_path": "/proj/work"
                        "mac_path": "/proj/work"
                        "windows_path": None
                    }
                    "data": {
                        "code": "data",
                        "type": "LocalStorage",
                        "id": 456
                        "linux_path": "/proj/data"
                        "mac_path": "/proj/data"
                        "windows_path": None
                    }
                },
                ["data2", "data3"]
            )

        In the example above, 4 storage roots are defined by the configuration:
        "work", "data", "data2", and "data3". The "work" and "data" roots can
        be associated with a SG local storage. The other two roots have no
        corresponding local storage in SG.

        :param: A shotgun connection
        :returns: A tuple of information about local storages mapped to the
            configuration's required storage roots.
        """

        log.debug(
            "Attempting to associate required storage roots with SG local "
            "storages..."
        )

        # build a lookup of storage root name to local storages SG dicts
        local_storage_lookup = {}

        # keep a list of storages that could not be mapped to a SG local storage
        unmapped_root_names = []

        # query all local storages from SG so we can store a lookup of roots
        # defined here to SG storages

        # fields required for SG local storage queries
        local_storage_fields = ["code", "id"]
        local_storage_fields.extend(ShotgunPath.SHOTGUN_PATH_FIELDS)

        # create the SG connection and query
        log.debug("Querying SG local storages...")
        sg_storages = sg_connection.find(
            "LocalStorage",
            [],
            local_storage_fields
        )
        log.debug("Query returned %s storages." % (len(sg_storages, )))

        # create lookups of storages by name and id for convenience. we'll check
        # against each root's shotgun_storage_id first, falling back to the
        # name if the id mapping field is not defined.
        sg_storages_by_id = {s["id"]: s for s in sg_storages}
        sg_storages_by_name = {s["code"]: s for s in sg_storages}

        for root_name, root_info in self:

            # see if the shotgun storage id is specified explicitly in the
            # roots.yml file.
            root_storage_id = root_info.get("shotgun_storage_id")
            if root_storage_id and root_storage_id in sg_storages_by_id:
                # found a match. store it in the lookup
                sg_storage = sg_storages_by_id[root_storage_id]
                log.debug(
                    "Storage root %s explicitly associated with SG local "
                    "storage id %s (%s)" %
                    (root_name, root_storage_id, sg_storage)
                )
                local_storage_lookup[root_name] = sg_storage
                continue

            # if we're here, no storage is specified explicitly. fall back to
            # the storage name.
            if root_name in sg_storages_by_name:
                # found a match. store it in the lookup
                sg_storage = sg_storages_by_name[root_name]
                log.debug(
                    "Storage root %s matches SG local storage with same name "
                    "(%s)" % (root_name, sg_storage)
                )
                local_storage_lookup[root_name] = sg_storage
                continue

            # if we're here, then we could not map the storage root to a local
            # storage in SG
            log.warning(
                "Storage root %s could not be mapped to a SG local storage" %
                (root_name,)
            )
            unmapped_root_names.append(root_name)

        # return a tuple of the processed info
        return local_storage_lookup, unmapped_root_names

    def populate_defaults(self):
        """
        This method ensures all sys.platforms are represented in all defined
        storage roots. If the platform key does not exist, it will be added to
        the metadata and set to None.

        If there are no roots defined, this method will create a default root
        definition.
        """
        if self.required:
            # there are roots required by this configuration. ensure all are
            # populated with the expected platform keys
            for root_name, root_info in self:
                for platform_key in self.PLATFORM_KEYS:

                    if platform_key not in root_info:
                        # platform key not defined for root. add it
                        root_info[platform_key] = None
        else:

            # no roots required by this configuration. add a default storage
            # requirement
            root_name = self.LEGACY_DEFAULT_STORAGE_NAME
            root_info = {
                "description": "Default location where project data is stored.",
                "mac_path": "/studio/projects",
                "linux_path": "/studio/projects",
                "windows_path": "\\\\network\\projects",
                "default": "true",
            }

            self._default_storage_name = root_name
            self._storage_roots_metadata[root_name] = root_info
            self._shotgun_paths_lookup[root_name] = \
                ShotgunPath.from_shotgun_dict(root_info)

    ############################################################################
    # protected methods

    def _init_from_config(self, config_folder):

        log.debug(
            "Initializing storage roots object. "
            "Supplied config folder: %s" %
            (config_folder,)
        )

        # ---- set some basic data for the object

        # the supplied roots folder, just in case
        self._config_root_folder = config_folder

        # the full path to the roots file for debugging/messages
        self._storage_roots_file = os.path.join(
            self._config_root_folder,
            self.STORAGE_ROOTS_FILE_PATH
        )

        log.debug(
            "Storage roots file defined in the config: %s" %
            (self._storage_roots_file,)
        )

        # load the roots file and store the metadata
        if os.path.exists(self._storage_roots_file):
            roots_metadata = _get_storage_roots_metadata(
                self._storage_roots_file)
        else:
            # file does not exist. we will initialize with an empty dict
            roots_metadata = {}

        self._process_metadata(roots_metadata)

    def _process_metadata(self, roots_metadata):

        log.debug("Storage roots metadata: %s" % (roots_metadata,))

        # store it on the object
        self._storage_roots_metadata = roots_metadata

        # ---- store information about the roots for easy access

        log.debug("Processing required storages defined by the config...")

        # iterate over each storage root required by the configuration. try to
        # identify the default root.
        for root_name, root_info in self:

            log.debug("Processing storage: %s - %s" % (root_name, root_info))

            # store a shotgun path for each root definition. sanitize path data
            # by passing it through the ShotgunPath object. if the configuration
            # has not been installed, these paths may be None.
            self._shotgun_paths_lookup[root_name] = \
                ShotgunPath.from_shotgun_dict(root_info)

            # check to see if this root is marked as the default
            if root_info.get("default", False):
                log.debug(
                    "Storage root %s explicitly marked as the default." %
                    (root_name,)
                )
                self._default_storage_name = root_name

        # no default storage root defined explicitly
        if not self._default_storage_name:

            log.debug("No default storage explicitly defined...")

            # if there is only one, then that is the default
            if len(roots_metadata) == 1:
                sole_storage_root = roots_metadata.keys()[0]
                log.debug(
                    "Storage %s identified as the default root because it is "
                    "the only root required by the configuration" %
                    (sole_storage_root,)
                )
                self._default_storage_name = sole_storage_root
            elif self.LEGACY_DEFAULT_STORAGE_NAME in roots_metadata:
                # legacy primary storage name defined. that is the defautl
                log.debug(
                    "Storage %s identified as the default root because it "
                    "matches the legacy default root name." %
                    (self.LEGACY_DEFAULT_STORAGE_NAME,)
                )
                self._default_storage_name = self.LEGACY_DEFAULT_STORAGE_NAME
            else:
                # default storage will be None
                log.warning(
                    "Unable to identify a default storage root in the config's "
                    "required storages."
                )


################################################################################
# internal util methods

def _get_storage_roots_metadata(storage_roots_file):
    """
    Parse the supplied storage roots file

    :param storage_roots_file: Path to the roots file.

    :return: The parsed metadata as a dictionary.
    """

    log.debug(
        "Reading storage roots file form disk: %s" %
        (storage_roots_file,)
    )

    try:
        # keep a handle on the raw metadata read from the roots file
        roots_metadata = yaml_cache.g_yaml_cache.get(
            storage_roots_file,
            deepcopy_data=False
        ) or {}  # if file is empty, initialize with empty dict
    except Exception as e:
        raise TankError(
            "Looks like the roots file is corrupt. "
            "Please contact support! "
            "File: '%s'. "
            "Error: %s" % (storage_roots_file, e)
        )

    log.debug("Read metadata: %s" % (roots_metadata,))

    return roots_metadata
