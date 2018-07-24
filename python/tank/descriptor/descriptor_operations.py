# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

from .. import hook


class DescriptorOperations(object):

    def __init__(self, shotgun, pc_id, config_descriptor):

        # Figure out if there is a core hook for descriptors.
        hook_path = os.path.join(
            config_descriptor.get_config_folder(), "core", "hooks", "descriptor_operations.py"
        )
        # If there is one, we'll create a hook instance so clients can share state between
        # calls
        if os.path.isfile(hook_path):
            self._hook_instance = hook.create_hook_instance([hook_path], parent=None)
            self._hook_instance.shotgun = shotgun
            self._hook_instance.pipeline_configuration_id = pc_id
            self._hook_instance.config_descriptor = config_descriptor
            if hasattr(self._hook_instance, "init"):
                self._hook_instance.init()
        else:
            self._hook_instance = None

    def download_local(self, descriptor):
        """
        Downloads the descriptor's content locally.

        If there is a descriptor hook in the config and it implements the download_local method, the
        bundle will be downloaded through it.
        """
        if self._hook_instance and hasattr(self._hook_instance, "download_local"):
            self._hook_instance.download_local(descriptor)
        else:
            descriptor.download_local()

    def ensure_local(self, descriptor):
        # Look in the config if there is a create_descriptor hook.
        if descriptor.exists_local() is False:
            self.download_local(descriptor)
