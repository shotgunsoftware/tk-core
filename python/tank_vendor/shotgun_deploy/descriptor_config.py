# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

from .descriptor import Descriptor

class ConfigDescriptor(Descriptor):

    def __init__(self, io_descriptor):
        super(ConfigDescriptor, self).__init__(io_descriptor)

    def get_version_constraints(self):
        """
        Returns a dictionary with version constraints. The absence of a key
        indicates that there is no defined constraint. The following keys can be
        returned: min_sg, min_core, min_engine and min_desktop
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
        # @TODO - implement!


    def resolve_storages(self):
        """
        Validate that the roots exist in shotgun. Communicates with Shotgun.

        Returns the root paths from shotgun for each storage.

        {
          "primary" : { "description": "Description",
                        "exists_on_disk": False,
                        "defined_in_shotgun": True,
                        "shotgun_id": 12,
                        "darwin": "/mnt/foo",
                        "win32": "z:\mnt\foo",
                        "linux2": "/mnt/foo"},

          "textures" : { "description": None,
                         "exists_on_disk": False,
                         "defined_in_shotgun": True,
                         "shotgun_id": 14,
                         "darwin": None,
                         "win32": "z:\mnt\foo",
                         "linux2": "/mnt/foo"}
        }

        The main dictionary is keyed by storage name. It will contain one entry
        for each local storage which is required by the configuration template.
        Each sub-dictionary contains the following items:

        - description: Description what the storage is used for. This comes from the
          configuration template and can be used to help a user to explain the purpose
          of a particular storage required by a configuration.
        - defined_in_shotgun: If false, no local storage with this name exists in Shotgun.
        - shotgun_id: If defined_in_shotgun is True, this will contain the entity id for
          the storage. If defined_in_shotgun is False, this will be set to none.
        - darwin/win32/linux: Paths to storages, as defined in Shotgun. These values can be
          None if a storage has not been defined.
        - exists_on_disk: Flag if the path defined for the current operating system exists on
          disk or not.

        :returns: dictionary with storage breakdown, see example above.
        """
        # @todo - implement
