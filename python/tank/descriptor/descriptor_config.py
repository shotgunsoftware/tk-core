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

from tank_vendor import yaml

from ..errors import TankFileDoesNotExistError
from . import constants
from .errors import TankInvalidInterpreterLocationError
from .descriptor import Descriptor
from .. import LogManager
from ..util import ShotgunPath

log = LogManager.get_logger(__name__)


class ConfigDescriptor(Descriptor):
    """
    Descriptor that describes a Toolkit Configuration
    """

    @property
    def associated_core_descriptor(self):
        """
        The descriptor dict or url required for this core or ``None`` if not defined.

        :returns: Core descriptor dict or uri or ``None`` if not defined
        """
        raise NotImplementedError("ConfigDescriptor.associated_core_descriptor is not implemented.")

    @property
    def python_interpreter(self):
        """
        Retrieves the Python interpreter for the current platform from the interpreter files.

        :raises TankFileDoesNotExistError: If the interpreter file is missing.
        :raises TankInvalidInterpreterLocationError: If the interpreter can't be found on disk.

        :returns: Path value stored in the interpreter file.
        """
        raise NotImplementedError("ConfigDescriptor.python_interpreter is not implemented.")

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

        manifest = self._get_manifest()

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
        readme_content = []

        readme_file = os.path.join(
            self._get_config_folder(),
            constants.CONFIG_README_FILE
        )
        if os.path.exists(readme_file):
            with open(readme_file) as fh:
                for line in fh:
                    readme_content.append(line.strip())

        return readme_content

    def _get_config_folder(self):
        """
        Returns the folder in which the configuration files are located.

        Derived classes need to implement this method or a ``NotImplementedError`` will be raised.

        :returns: Path to the configuration files folder.
        """
        raise NotImplementedError("ConfigDescriptor._get_config_folder is not implemented.")

    def _get_current_platform_interpreter_file_name(self, install_root):
        """
        Retrieves the path to the interpreter file for a given install root.

        :param str install_root: This can be the root to a studio install for a core
            or a pipeline configuration root.

        :returns: Path for the current platform's interpreter file.
        :rtype: str
        """
        return ShotgunPath.get_file_name_from_template(
            os.path.join(install_root, "core", "interpreter_%s.cfg")
        )

    def _find_interpreter_location(self, path):
        """
        Finds the interpreter file in a given ``config`` folder.

        This is a helper method for derived classes.

        :param path: Path to a config folder, which traditionally has ``core``
            and ``env`` subfolders.

        :returns: Path to the Python interpreter.
        """
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
        # get the roots definition
        root_file_path = os.path.join(
            self._get_config_folder(),
            "core",
            constants.STORAGE_ROOTS_FILE)

        roots_data = {}

        if os.path.exists(root_file_path):
            with open(root_file_path, "r") as root_file:
                # if file is empty, initializae with empty dict...
                roots_data = yaml.load(root_file) or {}

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
