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
import sys
import subprocess

from .base import IODescriptorBase
from ..errors import TankDescriptorError
from ... import LogManager

log = LogManager.get_logger(__name__)


class IODescriptorRezException(Exception):
    """IODescriptorRez Exception"""


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

    def __init__(self, descriptor_dict, sg_connection, bundle_type):
        """
        Constructor

        :param descriptor_dict: descriptor dictionary describing the bundle
        :param sg_connection: Shotgun connection to associated site.
        :param bundle_type: Either AppDescriptor.APP, CORE, ENGINE or FRAMEWORK.
        :return: Descriptor instance
        """

        super(IODescriptorRez, self).__init__(descriptor_dict, sg_connection,
                                              bundle_type)

        self._validate_descriptor(
            descriptor_dict,
            required=["type", "package"],
            optional=["name", "packages", "version"]
        )

        self._version = descriptor_dict.get("version")
        package = descriptor_dict["package"]
        if '-' in package:
            # package looks as "foo-0.1.0"
            package_data = package.split('-')
            if len(package_data) != 2:
                raise IODescriptorRezException(
                    'Package name "{}" is invalid.'.format(package))

            self._package = package_data[0]
            if not self._version:
                self._version = package_data[1]
            else:
                raise IODescriptorRezException(
                    'Version has been defined twice in "package" field '
                    'and "version" field for:\n{}'
                    ''.format(self._descriptor_dict))
        else:
            # package looks as "foo"
            self._package = package

        if self._version:
            if 'v' in self._version.lower():
                raise IODescriptorRezException(
                    'Version is "{}" invalid. It should not has "v".'.format(
                        self._version))
            package_with_version = '{}-{}'.format(self._package, self._version)
        else:
            package_with_version = self._package

        self._packages = descriptor_dict.get("packages")
        # Append package with version to required packages list.
        if not self._packages:
            self._packages = [package_with_version]
        else:
            if package_with_version not in self._packages:
                self._packages.append(package_with_version)

        # lastly, resolve environment variables and ~
        self._path = self._get_resolved_path()

        # if there is a name defined in the descriptor dict then lets use
        # this, otherwise we'll fall back to the folder name:
        self._name = descriptor_dict.get("name")
        if not self._name:
            # fall back to the folder name
            bn = os.path.basename(self._path)
            self._name, _ = os.path.splitext(bn)

    def _get_resolved_path(self):
        # Add rez python module to sys.path
        self._append_sys_path_with_rez_loc()

        from rez.resolved_context import ResolvedContext

        context = ResolvedContext(self._packages)
        resolved_package = context.get_resolved_package(self._package)
        if not resolved_package:
            from pprint import pformat
            raise ImportError('Failed to resolve rez package for:\n{}'.format(
                pformat(self._descriptor_dict)))
        return os.path.normpath(resolved_package.root)

    def _get_rez_location(self):
        """
        Checks to see if a Rez package is available in the current environment.
        If it is available, add it to the system path, exposing the Rez
        Python API
        :returns: A path to the Rez package.
        """
        rez_path = self._get_resolved_rez_variables('REZ_REZ_ROOT')
        return rez_path

    def _append_sys_path_with_rez_loc(self):
        try:
            import rez
        except ImportError:
            # Using format instead of os.path.join, else would got sys.path
            # issue
            rez_python_lib = '{}/{}/{}'.format(self._get_rez_location(), 'lib',
                                               'site-packages')
            log.debug('Appending {} to sys.path.'.format(rez_python_lib))
            sys.path.append(rez_python_lib)

    def _get_resolved_rez_variables(self, variable, strict=True):
        system = sys.platform
        if system == "win32":
            rez_cmd = 'rez-env rez -- echo %{}%'.format(variable)
        else:
            rez_cmd = 'rez-env rez -- printenv {}'.format(variable)
        process = subprocess.Popen(rez_cmd, stdout=subprocess.PIPE, shell=True)
        rez_path, err = process.communicate()
        if err or not rez_path:
            if strict:
                raise ImportError(
                    "Failed to find Rez as a package in the current "
                    "environment! Try 'rez-bind rez'!")
            else:
                print >> sys.stderr, (
                    "WARNING: Failed to find a Rez package in the current "
                    "environment. Unable to request Rez packages.")
            rez_path = ""
        else:
            rez_path = '{}'.format(rez_path.strip().replace('\\', '/'))
        return rez_path

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
            raise TankDescriptorError(
                "%s does not point at a valid bundle on disk!" % self)

    def is_immutable(self):
        """
        Returns true if this items content never changes
        """
        return False

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
        log.debug(
            "Clone cache for %r: Not copying anything for this descriptor type")

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
