# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from .action_base import Action
from ..util import filesystem


class CopyAppsLocalAction(Action):
    """
    Action for copying apps to a local cache repository
    """
    def __init__(self):
        Action.__init__(
            self,
            "create_local_bundle_cache",
            Action.TK_INSTANCE,
            "Creates a bundle cache fallback location and ensures all apps are cached.",
            "Configuration")

        # this method can be executed via the API
        self.supports_api = True

        # no tank command support for this one
        self.supports_tank_command = False

        self.parameters = {}

        self.parameters["path"] = {
            "description": "Path to cache into.",
            "default": None,
            "type": "str",
        }

    def run_noninteractive(self, log, parameters):
        """
        Tank command API accessor. 
        Called when someone runs a tank command through the core API.
        
        :param log: std python logger
        :param parameters: dictionary with tank command parameters
        """
        computed_params = self._validate_parameters(parameters)
        path = computed_params["path"]

        log.debug("making sure '%s' exists" % path)
        filesystem.ensure_folder_exists(path)

        # get list of descriptors
        descriptors = {}
        updated_descriptors = []

        for env_name in self.tk.pipeline_configuration.get_environments():
            env = self.tk.pipeline_configuration.get_environment(env_name)
            for eng in env.get_engines():

                desc = env.get_engine_descriptor(eng)
                descriptors[desc.get_uri()] = desc

                for app in env.get_apps(eng):
                    desc = env.get_app_descriptor(eng, app)
                    descriptors[desc.get_uri()] = desc

            for framework in env.get_frameworks():
                desc = env.get_framework_descriptor(framework)
                descriptors[desc.get_uri()] = desc

        # cache them all out
        for descriptor in descriptors.itervalues():
            if descriptor.clone_cache(path):
                log.debug("Updated '%s' with %s" % (path, descriptor))
                updated_descriptors.append(descriptor)

        return updated_descriptors
