# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
from .path import IODescriptorPath
from ..errors import TankDescriptorError
from ...util import ShotgunPath
from ... import LogManager

log = LogManager.get_logger(__name__)


class IODescriptorVersionedPath(IODescriptorPath):
    """
    Represents a local item on disk. This item is never downloaded
    into the local storage. Rather, the versions should already be available
    on disk in versioned folders, which this class will resolve:

    In its most basic form, just feed it the parent directory for an app.
    It will resolve the latest version
        {"type": "versioned_path", "path": "/path/to/app"}

    You can specify particular versions, or simple version patterns:

        {"type": "versioned_path",
        "path": "/path/to/app",
        "version": "v1.2.3"}

        Resolves to latest version in "path": "/path/to/app/v1.2.3"

        {"type": "versioned_path",
        "path": "/path/to/app",
        "version": "v1.x.x"}

        Resolves to the latest version of the v1.X tree in "path": "/path/to/app/v1.2.3"

    It can resolve os-specific paths:
        {"type": "versioned_path",
         "linux_path": "/path/to/app",
         "windows_path": "d:\foo\bar",
         "mac_path": "/path/to/app" }

    You can use a version token if you need to define a more complex path:

    {"type": "versioned_path",
     "path": "/path/to/app/{version}/RunMe.exe"}

    Name is optional and if not specified will be determined based on folder path.
    If name is not specified and path is /tmp/foo/bar, the name will set to 'bar'.

    If no version token is provided, the resolved version will be appended to the end
    of the path.

    """

    VERSION_TOKEN = "{version}"

    def __init__(self, descriptor_dict):
        """
        Constructor

        :param descriptor_dict: descriptor dictionary describing the bundle
        :return: Descriptor instance
        """

        super(IODescriptorPath, self).__init__(descriptor_dict)

        self._validate_descriptor(
            descriptor_dict,
            required=["type"],
            optional=["name", "linux_path", "mac_path", "path", "windows_path", "version"]
        )

        self._initDescriptor = descriptor_dict

        # platform specific location support
        platform_key = ShotgunPath.get_shotgun_storage_key()

        # Make sure the given version matches the version pattern

        self._rawPath = None

        if "path" in descriptor_dict:
            # first look for 'path' key
            self._rawPath = descriptor_dict["path"]
            self._multi_os_descriptor = False
        elif platform_key in descriptor_dict:
            # if not defined, look for os specific key
            self._rawPath = descriptor_dict[platform_key]
            self._multi_os_descriptor = True

        # Raise this if the path isn't set, or the path is empty
        if not self._rawPath:
            raise TankDescriptorError(
                "Invalid descriptor! Could not find a path or a %s entry in the "
                "descriptor dict %s." % (platform_key, descriptor_dict)
            )

        # if there is a name defined in the descriptor dict then lets use
        # this, otherwise we'll fall back to the folder name:
        self._name = descriptor_dict.get("name")
        if not self._name:
            # fall back to the folder name
            bn = os.path.basename(self._rawPath)
            self._name, _ = os.path.splitext(bn)

        # Check that the path as version token. If not, assume this is the root path
        # and the path contents are versioned folders
        if not self.VERSION_TOKEN in self._rawPath:
            log.debug('No version token found. Assuming path is version root.')
            self._rawPath = os.sep.join([self._rawPath, self.VERSION_TOKEN])

        self._parentPath = self._rawPath.split(self.VERSION_TOKEN)[0]

        # lastly, resolve environment variables and ~
        self._rawPath = os.path.expandvars(self._rawPath)
        self._rawPath = os.path.expanduser(self._rawPath)

        # and normalize:
        self._rawPath = os.path.normpath(self._rawPath)
        self._version = descriptor_dict.get("version")

        if self._version == 'latest':
            self._version = None

        self._version = self._get_latest_version_tag(constraint_pattern=self._version)
        log.debug(self._version)

        self._path = self._rawPath.replace(self.VERSION_TOKEN, self._version)
        log.debug("DESCRIPTOR: %s" % self._path)

    def _get_latest_version_tag(self, constraint_pattern=None):
        versions = self._get_versions_in_path(self._parentPath)

        if not versions:
            raise TankDescriptorError("Unable to find any versions in %s." % self._parentPath)

        latestTag = self._find_latest_tag_by_pattern(versions, constraint_pattern)

        if latestTag is None:
            raise TankDescriptorError("Unable to find versions in '%s' that matched constraint pattern: '%s'." % (self._parentPath, constraint_pattern))

        return latestTag

    def _get_bundle_cache_path(self, bundle_cache_root):
        """
        Given a cache root, compute a cache path suitable
        for this descriptor, using the 0.18+ path format.

        :param bundle_cache_root: Bundle cache root path
        :return: Path to bundle cache location
        """
        return self._path

    def _get_cache_paths(self):
        """
        Get a list of resolved paths, starting with the primary and
        continuing with alternative locations where it may reside.

        Note: This method only computes paths and does not perform any I/O ops.

        :return: List of path strings
        """
        return [self._path]

    def get_system_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk, e.g. 'tk-maya'
        """
        return self._name

    def get_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.

        :param constraint_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:

                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                - v0.12.x - get the highest v0.12 version
                - v1.x.x - get the highest v1 version

        :returns: IODescriptorPath object
        """

        descriptor_dict = self._initDescriptor.copy()
        descriptor_dict["version"] = self._get_latest_version_tag(constraint_pattern)
        return IODescriptorVersionedPath(descriptor_dict)

    def get_latest_cached_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version
        that is locally available in the bundle cache search path.

        :param constraint_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:

                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                - v0.12.x - get the highest v0.12 version
                - v1.x.x - get the highest v1 version

        :returns: instance deriving from IODescriptorBase or None if not found
        """
        # The path *is* the local cache, and the only repo available.
        return self.get_latest_version(constraint_pattern)

    def get_version(self):
        """
        Returns the version number string for this item
        """
        # version number does not make sense for this type of item
        # so a fixed string is returned
        return self._version

    def download_local(self):
        """
        Retrieves this version to local repo
        """
        # ensure that this exists on disk
        if not self.exists_local():
            raise TankDescriptorError("%s does not point at a valid bundle on disk!" % self)

    def is_immutable(self):
        """
        Returns true if this items content never changes
        """
        return False

    def clone_cache(self, cache_root):
        """
        The descriptor system maintains an internal cache where it downloads
        the payload that is associated with the descriptor. Toolkit supports
        complex cache setups, where you can specify a series of path where toolkit
        should go and look for cached items.

        This is an advanced method that helps in cases where a user wishes to
        administer such a setup, allowing a cached payload to be copied from
        its current location into a new cache structure.

        If the descriptor's payload doesn't exist on disk, it will be downloaded.

        :param cache_root: Root point of the cache location to copy to.
        """
        # no payload is cached at all, so nothing to do
        log.debug("Clone cache for %r: Not copying anything for this descriptor type")

    def has_remote_access(self):
        """
        Probes if the current descriptor is able to handle
        remote requests. If this method returns, true, operations
        such as :meth:`download_local` and :meth:`get_latest_version`
        can be expected to succeed.

        :return: True if a remote is accessible, false if not.
        """
        # the remote is the same as the cache for path descriptors
        return True

    def get_path(self):
        return self._path