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
import re

from .perforce import IODescriptorPerforce, TankPerforceError, _check_output
from ... import LogManager

try:
    from tank_vendor import sgutils
except ImportError:
    from tank_vendor import six as sgutils

log = LogManager.get_logger(__name__)


class IODescriptorPerforceLabel(IODescriptorPerforce):
    """
    Represents a label in perforce, belonging to a particular depot.

    Label format:
    location: {"type": "perforce_label",
               "path": "//path/to/stream",
               "label": "v1.0.0"}

    The payload cached in the bundle cache represents a Label in the depot, and the label
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
            descriptor_dict, required=["type", "path", "label"], optional=[]
        )

        self._cache_type = "perforce_label"

        # call base class
        super(IODescriptorPerforceLabel, self).__init__(
            descriptor_dict, sg_connection, bundle_type
        )

        # path is handled by base class
        self._sg_connection = sg_connection
        self._bundle_type = bundle_type
        self._version = descriptor_dict.get("label")

    def __str__(self):
        """
        Human-readable representation
        """
        # //DEPOT/Appstore/tk-multi-loader2, Perforce Label 123456
        return "%s, Perforce Label %s" % (self._path, self._version)

    def get_version(self):
        """
        Returns the version number string for this item, .e.g 'v1.2.3'
        """
        return self._version

    def get_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.

        :param constraint_pattern: If this is specified, the query will be constrained
        by the given pattern. Version patterns are on the following forms:

            - v1.2.3 (means the descriptor returned will inevitably be same as self)
            - v1.2.x
            - v1.x.x

        :returns: IODescriptorManual object
        """

        p4_labels = self._fetch_labels()
        labels_list = list(p4_labels.keys())
        latest_label = self._find_latest_tag_by_pattern(labels_list, pattern=None)
        if latest_label is None:
            raise TankPerforceError(
                "Perforce depot %s doesn't have any tags!" % self._path
            )

        # make a new descriptor
        new_loc_dict = copy.deepcopy(self._descriptor_dict)
        new_loc_dict["label"] = sgutils.ensure_str(latest_label)
        desc = IODescriptorPerforceLabel(
            new_loc_dict, self._sg_connection, self._bundle_type
        )
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)
        log.debug("Latest version resolved to %r" % desc)
        return desc

    def _fetch_labels(self):
        """
        Get the labels semantic versions and full label name from perforce.

        {
            "v1.0.1": "bundleA-v1.0.1",
            "v2.0.0": "bundleA-v1.0.0",
            "v3.2.1": "bundleA_beta-v3.2.1"
            "v4.0.0": "v4.0.0"
        }

        :returns: dict
        """
        try:
            # query labels for this depot path
            commands = ["p4", "labels", "%s/..." % self._path]
            output = _check_output(commands)
            # Expected result:
            #   Label tk-multi-app-v1.0.1 2024/11/29 'Created by User.Name.'
            #   Label v1.0.0 2024/11/29 'Created by User.Name.'

            p4_labels = {}
            # Map the found version to the source label name for sorting.
            for line in output.splitlines():
                if line.startswith("Label "):
                    # Extract the label name from lines like: "Label label_name date description"
                    parts = line.split()
                    label_name = parts[1]
                    # Typically labels are global for the depot, so labels
                    # maybe prepended by more data, try to extract the version
                    regex = re.compile(r"v\d+\.\d+\.\d+")
                    m = regex.match(sgutils.ensure_str(label_name))
                    if m:
                        p4_labels[m.group(1)] = label_name

        except Exception as e:
            raise TankPerforceError(
                "Could not get list of labels for %s: %s" % (self._path, e)
            )

        if len(p4_labels.keys()) == 0:
            raise TankPerforceError(
                "Depot path %s doesn't have any labels!" % self._path
            )

        return p4_labels

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
        all_versions = self._get_locally_cached_versions()
        version_numbers = list(all_versions.keys())

        if not version_numbers:
            return None

        version_to_use = self._find_latest_tag_by_pattern(
            version_numbers, constraint_pattern
        )
        if version_to_use is None:
            return None

        # make a descriptor dict
        new_loc_dict = copy.deepcopy(self._descriptor_dict)
        new_loc_dict["label"] = sgutils.ensure_str(version_to_use)
        desc = IODescriptorPerforceLabel(
            new_loc_dict, self._sg_connection, self._bundle_type
        )
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)
        log.debug("Latest version resolved to %r" % desc)
        return desc
