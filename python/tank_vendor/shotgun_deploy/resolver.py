# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import sys

from . import util
from . import Descriptor, create_descriptor
from . import constants

from .configuration import create_managed_configuration, create_unmanaged_configuration

log = util.get_shotgun_deploy_logger()

class ConfigurationResolver(object):
    """
    Base class for defining recipies for how to resolve a configuration object
    given a particular project and configuration.
    """

    def __init__(self, sg_connection, bundle_cache_root, pipeline_config_name, base_config_location):
        """
        Constructor

        :param sg_connection: Shotgun API instance
        :param bundle_cache_root: Root where content should be cached
        :param pipeline_config_name: Name of configuration branch (e.g Primary)
        :param base_config_location: Location dict or string for fallback config.
        """
        self._sg_connection = sg_connection
        self._bundle_cache_root = bundle_cache_root
        self._pipeline_config_name = pipeline_config_name
        self._base_config_location = base_config_location

    def resolve_project_configuration(self, project_id):
        """
        Given a Shotgun project (or None for site mode), return a configuration
        object based on a particular set of resolution logic rules.

        This method needs to be subclassed by different methods, implementing different
        business logic for resolve. This resolve may include different type of fallback
        schemes, simple non-shotgun schemes etc.

        :param project_id: Project id to create a config object for, None for the site config.
        :return: Configuration instance
        """
        raise NotImplementedError





class BasicConfigurationResolver(ConfigurationResolver):
    """
    Basic configuration resolves which implements the logic
    toolkit is using today.
    """

    def __init__(self, sg_connection, bundle_cache_root, pipeline_config_name, base_config_location):
        """
        Constructor

        :param sg_connection: Shotgun API instance
        :param bundle_cache_root: Root where content should be cached
        :param pipeline_config_name: Name of configuration branch (e.g Primary)
        :param base_config_location: Location dict or string for fallback config.
        """
        super(BasicConfigurationResolver, self).__init__(
            sg_connection,
            bundle_cache_root,
            pipeline_config_name,
            base_config_location
        )

    def resolve_project_configuration(self, project_id):
        """
        Given a Shotgun project (or None for site mode), return a configuration
        object based on a particular set of resolution logic rules.

        This method needs to be subclassed by different methods, implementing different
        business logic for resolve. This resolve may include different type of fallback
        schemes, simple non-shotgun schemes etc.

        :param project_id: Project id to create a config object for, None for the site config.
        :return: Configuration instance
        """
        # now resolve pipeline config details
        project_entity = None if project_id is None else {"type": "Project", "id": project_id}

        # find a pipeline configuration in Shotgun.
        log.debug("Checking pipeline configuration in Shotgun...")
        pc_data = self._sg_connection.find_one(
            constants.PIPELINE_CONFIGURATION_ENTITY,
            [["code", "is", self._pipeline_config_name],
             ["project", "is", project_entity]],
            ["mac_path",
             "windows_path",
             "linux_path",
             constants.SHOTGUN_PIPELINECONFIG_URI_FIELD]
        )
        log.debug("Shotgun returned: %s" % pc_data)

        lookup_dict = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path"}

        if pc_data and pc_data.get(lookup_dict[sys.platform]):
            # we have paths specified for the local platform!
            return create_managed_configuration(
                self._sg_connection,
                self._bundle_cache_root,
                project_id,
                pc_data.get("id"),
                pc_data.get("windows_path"),
                pc_data.get("linux_path"),
                pc_data.get("mac_path"),
            )

        elif pc_data.get(constants.SHOTGUN_PIPELINECONFIG_URI_FIELD):
            uri = pc_data.get(constants.SHOTGUN_PIPELINECONFIG_URI_FIELD)
            log.debug("Attempting to resolve config uri %s" % uri)

            cfg_descriptor = create_descriptor(
                self._sg_connection,
                Descriptor.CONFIG,
                uri,
                self._bundle_cache_root
            )

            return create_unmanaged_configuration(
                self._sg_connection,
                self._bundle_cache_root,
                cfg_descriptor,
                project_id,
                pc_data.get("id")
            )

        # fall back on base
        return self._create_base_configuration(project_id)


    def _create_base_configuration(self, project_id):
        """
        Helper method that creates a config wrapper object

        :param project_id:
        :return:
        """
        cfg_descriptor = create_descriptor(
            self._sg_connection,
            Descriptor.CONFIG,
            self._base_config_location,
            self._bundle_cache_root
        )

        log.debug("Creating a configuration wrapper based on %r." % cfg_descriptor)

        # create an object to represent our configuration install
        return create_unmanaged_configuration(
            self._sg_connection,
            self._bundle_cache_root,
            cfg_descriptor,
            project_id,
            pipeline_config_id=None
        )
