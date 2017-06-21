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

from . import constants
from .errors import TankDescriptorError
from .descriptor_config_base import ConfigDescriptorBase
from .. import LogManager

log = LogManager.get_logger(__name__)


class ConfigDescriptor(ConfigDescriptorBase):
    """
    Descriptor that describes a Toolkit Configuration
    """

    def _get_config_folder(self):
        """
        Returns the folder in which the configuration files are located.

        :returns: Path to the configuration files folder.
        """
        self._io_descriptor.ensure_local()
        return self._io_descriptor.get_path()

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

    @property
    def python_interpreter(self):
        """
        Retrieves the Python interpreter for the current platform from the interpreter files at
        ``core/interpreter_Linux.cfg``, ``core/interpreter_Darwin.cfg`` or
        ``core/interpreter_Windows.cfg``.

        :returns: Path value stored in the interpreter file.
        """
        self._io_descriptor.ensure_local()
        return self._find_interpreter_location(self.get_path())
