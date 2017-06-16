# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import with_statement

import os
import sys

from tank_vendor import yaml

from ..errors import TankError, TankFileDoesNotExistError
from . import constants
from .errors import TankDescriptorError, TankInvalidInterpreterLocationError
from .descriptor_config_base import ConfigDescriptorBase
from .. import LogManager

log = LogManager.get_logger(__name__)


class ConfigDescriptor(ConfigDescriptorBase):
    """
    Descriptor that describes a Toolkit Configuration
    """

    def _get_config_folder(self):
        """
        """
        self._io_descriptor.ensure_local()
        return self._io_descriptor.get_path()

    @property
    def version_constraints(self):
        """
        A dictionary with version constraints. The absence of a key
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

    @property
    def readme_content(self):
        """
        Associated readme content as a list.
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

    @property
    def associated_core_descriptor(self):
        """
        The descriptor dict or url required for this core or None if not defined.

        :returns: Core descriptor dict or uri or None if not defined
        """
        core_descriptor_dict = None

        self._io_descriptor.ensure_local()

        core_descriptor_path = os.path.join(
            self._io_descriptor.get_path(),
            "core",
            constants.CONFIG_CORE_DESCRIPTOR_FILE
        )

        if os.path.exists(core_descriptor_path):
            # the core_api.yml contains info about the core config:
            #
            # location:
            #    name: tk-core
            #    type: app_store
            #    version: v0.16.34

            log.debug("Detected core descriptor file '%s'" % core_descriptor_path)

            # read the file first
            fh = open(core_descriptor_path, "rt")
            try:
                data = yaml.load(fh)
                core_descriptor_dict = data["location"]
            except Exception, e:
                raise TankDescriptorError(
                    "Cannot read invalid core descriptor file '%s': %s" % (core_descriptor_path, e)
                )
            finally:
                fh.close()

        return core_descriptor_dict

    def _get_current_platform_file_suffix(self):
        """
        Find the suffix for the current platform's configuration file.

        :returns: Suffix for the current platform's configuration file.
        :rtype: str
        """
        # Now find out the appropriate python interpreter file to search for
        if sys.platform == "darwin":
            return "Darwin"
        elif sys.platform == "win32":
            return "Windows"
        elif sys.platform.startswith("linux"):
            return "Linux"
        else:
            raise TankError("Unknown platform: %s." % sys.platform)

    def _get_current_platform_interpreter_file_name(self, install_root):
        """
        Retrieves the path to the interpreter file for a given install root.

        :param str install_root: This can be the root to a studio install for a core
            or a pipeline configuration root.

        :returns: Path for the current platform's interpreter file.
        :rtype: str
        """
        return os.path.join(
            install_root, "core", "interpreter_%s.cfg" % self._get_current_platform_file_suffix()
        )

    @property
    def python_interpreter(self):
        path = self.get_path()
        return self._find_interpreter_location(path)

    def _find_interpreter_location(self, path):

        # Find the interpreter file for the current platform.
        interpreter_config_file = self._get_current_platform_interpreter_file_name(
            path
        )

        if os.path.exists(interpreter_config_file):
            with open(interpreter_config_file, "r") as f:
                path_to_python = f.read().strip()

            if not path_to_python or not os.path.exists(path_to_python):
                raise TankInvalidInterpreterLocationError(
                    "Cannot find interpreter '%s' defined in "
                    "config file '%s'." % (path_to_python, interpreter_config_file)
                )
            else:
                return path_to_python
        else:
            raise TankFileDoesNotExistError(
                "No interpreter file for the current platform found at '%s'." % interpreter_config_file
            )

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

    @property
    def required_storages(self):
        """
        A list of storage names needed for this config.
        This may be an empty list if the configuration doesn't
        make use of the file system.

        :returns: List of storage names as strings
        """
        roots_data = self._get_roots_data()
        return roots_data.keys()
