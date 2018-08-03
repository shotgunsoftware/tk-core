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
import shutil
import sys
import subprocess

from .base import IODescriptorBase
from ..errors import TankDescriptorError
from ...util import ShotgunPath
from ... import LogManager

log = LogManager.get_logger(__name__)


class IODescriptorRez(IODescriptorBase):
    """
    Represents a local item on disk. This item is never downloaded
    into the local storage, you interact with it directly::

        {"type": "path", "path": "/path/to/app"}

    Optional parameters are possible::

        {"type": "path", "path": "/path/to/app", "name": "my-app"}

        {"type": "path",
         "linux_path": "/path/to/app",
         "windows_path": "d:\foo\bar",
         "mac_path": "/path/to/app" }

    Name is optional and if not specified will be determined based on folder path.
    If name is not specified and path is /tmp/foo/bar, the name will set to 'bar'
    """

    def __init__(self, descriptor_dict):
        """
        Constructor

        :param descriptor_dict: descriptor dictionary describing the bundle
        :return: Descriptor instance
        """

        super(IODescriptorRez, self).__init__(descriptor_dict)

        self._validate_descriptor(
            descriptor_dict,
            required=["type", "name"],
            optional=["version"]
        )

        self._name = descriptor_dict["name"]

        
        self._version = descriptor_dict.get("version")
        
        if self._version:
            # Shotgun expect version number to be prefixed with "v".
            # REZ don't, we'll support both but never pass the letter to rez.
            self._version = self._version.strip("v")

        # Resolve location
        self._path = self._get_rez_pkg_location()

    def _get_rez_pkg_location(self):
        
        request = "{0}-{1}".format(self._name, self._version) if self._version is not None else self._name
        log.debug("Resolved rez request is: {0}".format(request))
        
        if sys.platform == "win32":
            cmd = 'rez-env {pkg} -- echo %REZ_{NAME}_ROOT%'.format(pkg=request, NAME=self._name.upper())
        else:
            cmd = 'rez-env {pkg} -- printenv REZ_{NAME}_ROOT'.format(pkg=request, NAME=self._name.upper())
            
        log.debug("Executing command: {0}".format(cmd))
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        stdout, stderr = process.communicate()
        
        log.debug("stdout:\n{0}".format(stdout))
        log.debug("stderr:\n{0}".format(stderr))

        if stderr or not stdout:
            log.error(stdout)
            raise ImportError("Failed resolve request for {0}".format(request))

        path = stdout.strip()
        log.debug("Resulting path is: {0}".format(path))
        return path

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
        return True

    def get_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.

        :param constraint_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:

                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                - v0.12.x - get the highest v0.12 version
                - v1.x.x - get the highest v1 version

        :returns: IODescriptorRez object
        """
        # we are always the latest version :)
        return self

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
        # we are always the latest version
        # also assume that the payload always exists on disk.
        return self

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
        return False
