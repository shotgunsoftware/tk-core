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
from .descriptor import Descriptor, create_descriptor
from .. import LogManager
from ..util import ShotgunPath
from ..util.version import is_version_older
from .io_descriptor import descriptor_uri_to_dict

log = LogManager.get_logger(__name__)


class ConfigDescriptor(Descriptor):
    """
    Descriptor that describes a Toolkit Configuration
    """

    def __init__(self, sg_connection, bundle_cache_root, fallback_roots, io_descriptor):
        super(ConfigDescriptor, self).__init__(io_descriptor)
        self._cached_core_descriptor = None
        self._sg_connection = sg_connection
        self._bundle_cache_root = bundle_cache_root
        self._fallback_roots = fallback_roots

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

    def resolve_core_descriptor(self):
        """
        Resolves the :class:`CoreDescriptor` from :attr:`ConfigDescriptor.associated_core_descriptor`.

        :returns: The core descriptor if :attr:`ConfigDescriptor.associated_core_descriptor` is set,
            ``None`` otherwise.
        """
        if not self.associated_core_descriptor:
            return None

        if not self._cached_core_descriptor:
            self._cached_core_descriptor = create_descriptor(
                self._sg_connection,
                Descriptor.CORE,
                self.associated_core_descriptor,
                self._bundle_cache_root,
                self._fallback_roots,
                resolve_latest=False
            )

        return self._cached_core_descriptor

    def get_associated_core_feature_info(self, feature_name, default_value=None):
        """
        Retrieves information for a given feature in the manifest of the core.

        The ``default_value`` will be returned in the following cases:
            - a feature is missing from the manifest
            - the manifest is empty
            - the manifest is missing
            - there is no core associated with this configuration.

        :param str feature_name: Name of the feature to retrieve from the manifest.
        :param object default_value: Value to return if the feature is missing.

        :returns: The value for the feature if present, ``default_value`` otherwise.
        """
        if self.resolve_core_descriptor():
            return self.resolve_core_descriptor().get_feature_info(feature_name, default_value)
        return default_value

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
            self.get_config_folder(),
            constants.CONFIG_README_FILE
        )
        if os.path.exists(readme_file):
            with open(readme_file) as fh:
                for line in fh:
                    readme_content.append(line.strip())

        return readme_content

    def associated_core_version_less_than(self, version_str):
        """
        Attempt to determine if the associated core version is less than
        a given version. Returning True means that the associated core
        version is less than the given one, however returning False
        does not guarantee that the associated version is higher, it may
        also be an indication that a version number couldn't be determined.

        :param version_str: Version string, e.g. '0.18.123'
        :returns: true if core version is less, false otherwise
        """
        core_desc = self.associated_core_descriptor

        result = False
        if core_desc:
            # (note: returning None means we are tracking latest version)

            if isinstance(core_desc, str):
                # convert to dict
                core_desc = descriptor_uri_to_dict(core_desc)

            if core_desc["type"] == "app_store":
                if is_version_older(core_desc["version"], version_str):
                    result = True

        return result

    def get_config_folder(self):
        """
        Returns the folder in which the configuration files are located.

        Derived classes need to implement this method or a ``NotImplementedError`` will be raised.

        :returns: Path to the configuration files folder.
        """
        raise NotImplementedError("ConfigDescriptor.get_config_folder is not implemented.")

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
                path_to_python = os.path.expandvars(f.read().strip())

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
            self.get_config_folder(),
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
