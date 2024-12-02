# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.
import copy

from .perforce import IODescriptorPerforce, TankPerforceError, _check_output
from ... import LogManager

try:
    from tank_vendor import sgutils
except ImportError:
    from tank_vendor import six as sgutils

log = LogManager.get_logger(__name__)


def _find_latest_change(changelist):
    """
    Given a list of changelist strings, cast to ints and get the max value
    to determine the latest changelist.

    :return: latest changelist or None
    """

    changes = []
    for i in changelist:
        try:
            changes.append(int(i))
        except ValueError:
            pass

    return max(changes) if changes else None


class IODescriptorPerforceChange(IODescriptorPerforce):
    """
    Represents a changelist in perforce, belonging to a depot.

    Change format:
    location: {"type": "perforce_change",
               "path": "//path/to/stream",
               "changelist": "3156014"}


    The payload cached in the bundle cache represents a changelist at a path in the depot.
    """

    def __init__(self, descriptor_dict, sg_connection, bundle_type):
        """
        Constructor

        :param descriptor_dict: descriptor dictionary describing the bundle
        :param sg_connection: Shotgun connection to associated site.
        :param bundle_type: Either AppDescriptor.APP, CORE, ENGINE or FRAMEWORK.
        :return: Descriptor instance
        """
        # make sure all required fields are there
        self._validate_descriptor(
            descriptor_dict, required=["type", "path"], optional=["changelist"]
        )

        self._cache_type = "perforce_change"

        # call base class
        super(IODescriptorPerforceChange, self).__init__(
            descriptor_dict, sg_connection, bundle_type
        )

        # path is handled by base class
        self._sg_connection = sg_connection
        self._bundle_type = bundle_type
        if not descriptor_dict.get("changelist"):
            self._version = self._get_latest_changelist()
        else:
            self._version = descriptor_dict["changelist"]

    def __str__(self):
        """
        Human-readable representation
        """
        # //DEPOT/Appstore/tk-multi-loader2, Perforce changelist 123456
        return "%s, Perforce changelist %s" % (self._path, self._version)

    def get_version(self):
        """
        Returns the changelist number string for this item, .e.g '12345'
        """
        return self._version

    def _get_latest_changelist(self):
        """
        Retrieve the latest changelist for this path in the perforce depot.

        :return: The latest changelist.
        """

        changelist = None

        log.debug(f"Getting the latest changelist at {self._path}")
        try:
            commands = ['p4', 'changes', '-m', '1', f"{self._path}/..."]
            result = _check_output(commands)

            # Parse the changelist number from the output
            # command result: Change 12345 on 2024/11/28 by User.Name@Client 'Commit Message'
            if result.strip():
                parts = result.split(" ", 4)
                changelist = parts[1]

        except Exception as e:
            raise TankPerforceError(
                "Could not get latest changelist for %s: %s" % (self._path, e)
            )

        return changelist

    def get_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.

        This will connect to p4 depot.
        This will check the latest changelist of a depot path

        :param constraint_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:

                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                - v0.12.x - get the highest v0.12 version
                - v1.x.x - get the highest v1 version

        :returns: IODescriptorPerforceStream object
        """

        if constraint_pattern:
            log.warning(
                "%s does not handle constraint patterns. "
                "Latest version will be used." % self
            )

        latest_changelist = self._get_latest_changelist()

        # make a new descriptor
        new_loc_dict = copy.deepcopy(self._descriptor_dict)
        new_loc_dict["changelist"] = sgutils.ensure_str(latest_changelist)
        desc = IODescriptorPerforceChange(
            new_loc_dict, self._sg_connection, self._bundle_type
        )
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)
        return desc

    def get_latest_cached_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest changelist
        that is locally available in the bundle cache search path.

        :param constraint_pattern: Not implemented with changelist.

        :returns: instance deriving from IODescriptorBase or None if not found
        """
        all_versions = self._get_locally_cached_versions()
        changes = list(all_versions.keys())

        change_to_use = _find_latest_change(changes)
        if change_to_use is None:
            return None

        # make a descriptor dict
        new_loc_dict = copy.deepcopy(self._descriptor_dict)
        new_loc_dict["changelist"] = sgutils.ensure_str(change_to_use)
        desc = IODescriptorPerforceChange(
            new_loc_dict, self._sg_connection, self._bundle_type
        )
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)
        log.debug("Latest changelist resolved to %r" % desc)
        return desc