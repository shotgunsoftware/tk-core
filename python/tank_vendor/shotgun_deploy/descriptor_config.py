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

from . import constants
from .. import yaml
from .errors import ShotgunDeployError
from .descriptor import Descriptor
from . import util

log = util.get_shotgun_deploy_logger()

class ConfigDescriptor(Descriptor):
    """
    Descriptor that describes a Toolkit Configuration
    """

    def __init__(self, io_descriptor):
        """
        Constructor

        :param io_descriptor: Associated IO descriptor.
        """
        super(ConfigDescriptor, self).__init__(io_descriptor)

    def needs_installation(self):
        """
        Returns true if this config needs to be installed before
        it can be used.

        :returns: True if installation is required prior to use.
        """
        # immutable descriptors are always installed
        # dev and path descriptors return false
        return self._io_descriptor.is_immutable()

    def get_version_constraints(self):
        """
        Returns a dictionary with version constraints. The absence of a key
        indicates that there is no defined constraint. The following keys can be
        returned: min_sg, min_core, min_engine and min_desktop

        :returns: Dictionary with optional keys min_sg, min_core,
                  min_engine and min_desktop
        """
        constraints = {}

        manifest = self._io_descriptor.get_manifest()

        if manifest.get("requires_shotgun_version") is not None:
            constraints["min_sg"] = manifest.get("requires_shotgun_version")

        if manifest.get("requires_core_version") is not None:
            constraints["min_core"] = manifest.get("requires_core_version")

        return constraints

    def get_readme_content(self):
        """
        Get associated readme content as a list.
        If not readme exists, an empty list is returned

        :returns: list of strings
        """
        self._io_descriptor.ensure_local()
        readme_content = []

        readme_file = os.path.join(
            self._io_descriptor.get_path(),
            constants.CONFIG_README_FILE
        )
        if os.path.exists(readme_file):
            fh = open(readme_file)
            for line in fh:
                readme_content.append(line.strip())
            fh.close()

        return readme_content

    def get_associated_core_location(self):
        """
        Introspects a configuration and returns the required core version

        :returns: Core version string or None if undefined
        """
        core_location_dict = None

        self._io_descriptor.ensure_local()

        core_location_path = os.path.join(
            self._io_descriptor.get_path(),
            "core",
            constants.CONFIG_CORE_LOCATION_FILE
        )

        if os.path.exists(core_location_path):
            # the core_api.yml contains info about the core config:
            #
            # location:
            #    name: tk-core
            #    type: app_store
            #    version: v0.16.34

            log.debug("Detected core location file '%s'" % core_location_path)

            # read the file first
            fh = open(core_location_path, "rt")
            try:
                data = yaml.load(fh)
                core_location_dict = data["location"]
            except Exception, e:
                raise ShotgunDeployError(
                    "Cannot read invalid core location file '%s': %s" % (core_location_path, e)
                )
            finally:
                fh.close()

        return core_location_dict


    def _get_roots_data(self):
        """
        Returns roots.yml data for this config.
        If no root file can be loaded, {} is returned.

        :returns: Roots data yaml content, usually a dictionary
        """
        self._io_descriptor.ensure_local()

        # get the roots definition
        root_file_path = os.path.join(
            self._io_descriptor.get_path(),
            "core",
            constants.STORAGE_ROOTS_FILE)

        roots_data = {}

        if os.path.exists(root_file_path):
            root_file = open(root_file_path, "r")
            try:
                # if file is empty, initializae with empty dict...
                roots_data = yaml.load(root_file) or {}
            finally:
                root_file.close()

        return roots_data

    def get_required_storages(self):
        """
        Returns a list of storage names needed for this config.
        This may be an empty list if the configuration doesn't
        make use of the file system.

        :returns: List of storage names as strings
        """
        roots_data = self._get_roots_data()
        return roots_data.keys()

    def copy(self, target_folder):
        """
        Copy the config descriptor into the specified target location

        :param target_folder: Folder to copy the descriptor to
        """
        self._io_descriptor.copy(target_folder)
