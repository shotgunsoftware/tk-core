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
from .base import IODescriptorBase
from ... import LogManager
from ...util import filesystem
from ..errors import TankDescriptorError

log = LogManager.get_logger(__name__)


class IODescriptorManual(IODescriptorBase):
    """
    Represents a manually installed item.

    This descriptor type is largely deprecated. Please do not use.
    """

    def __init__(self, descriptor_dict, bundle_type):
        """
        Constructor

        :param descriptor_dict: descriptor dictionary describing the bundle
        :param bundle_type: The type of bundle. ex: Descriptor.APP
        :return: Descriptor instance
        """
        super(IODescriptorManual, self).__init__(descriptor_dict)

        self._validate_descriptor(
            descriptor_dict,
            required=["type", "name", "version"],
            optional=[]
        )

        self._type = bundle_type
        self._name = descriptor_dict.get("name")
        self._version = descriptor_dict.get("version")

    def _get_bundle_cache_path(self, bundle_cache_root):
        """
        Given a cache root, compute a cache path suitable
        for this descriptor, using the 0.18+ path format.

        :param bundle_cache_root: Bundle cache root path
        :return: Path to bundle cache location
        """
        return os.path.join(
            bundle_cache_root,
            "manual",
            self._name,
            self._version
        )

    def _get_cache_paths(self):
        """
        Get a list of resolved paths, starting with the primary and
        continuing with alternative locations where it may reside.

        Note: This method only computes paths and does not perform any I/O ops.

        :return: List of path strings
        """
        # get default cache paths from base class
        paths = super(IODescriptorManual, self)._get_cache_paths()

        # for compatibility with older versions of core, prior to v0.18.x,
        # add the old-style bundle cache path as a fallback. As of v0.18.x,
        # the bundle cache subdirectory names were shortened and otherwise
        # modified to help prevent MAX_PATH issues on windows. This call adds
        # the old path as a fallback for cases where core has been upgraded
        # for an existing project. NOTE: This only works because the bundle
        # cache root didn't change (when use_bundle_cache is set to False).
        # If the bundle cache root changes across core versions, then this will
        # need to be refactored.
        try:
            legacy_folder = self._get_legacy_bundle_install_folder(
                "manual",
                self._bundle_cache_root,
                self._type,
                self._name,
                self._version
            )
        except RuntimeError, e:
            # warn and continue
            log.warning("Could not add legacy location to bundle search path: %s" % e)
        else:
            paths.append(legacy_folder)

        return paths

    def get_system_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk, e.g. 'tk-maya'
        """
        return self._name

    def get_version(self):
        """
        Returns the version number string for this item, .e.g 'v1.2.3'
        """
        return self._version

    def download_local(self):
        """
        Retrieves this version to local repo
        """
        # ensure that this exists on disk
        if not self.exists_local():
            raise TankDescriptorError("%s does not exist on disk!")

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
        # since this descriptor has no way of updating and no way of knowing 
        # what is latest, just return our own version as representing the latest version.
        return self



