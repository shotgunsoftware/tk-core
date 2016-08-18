# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Resolver module. This module provides a way to resolve a pipeline configuration
on disk.
"""

import os
import fnmatch
import pprint

from ..descriptor import Descriptor, create_descriptor, descriptor_uri_to_dict
from .errors import TankBootstrapError
from .configuration import Configuration
from ..util import filesystem
from ..util import ShotgunPath
from ..util import LocalFileStorageManager
from .. import LogManager
from . import constants

log = LogManager.get_logger(__name__)


class ConfigurationResolver(object):
    """
    A class that contains the business logic for returning a configuration
    object given a set of parameters.
    """

    def __init__(
            self,
            entry_point,
            engine_name,
            project_id=None,
            bundle_cache_fallback_paths=None
    ):
        """
        Constructor

        :param entry_point: The entry point name of the system that is being bootstrapped.
        :param engine_name: Name of the engine that is about to be launched.
        :param project_id: Project id to create a config object for, None for the site config.
        :param bundle_cache_fallback_paths: Optional list of additional paths where apps are cached.
        """
        self._project_id = project_id
        self._entry_point = entry_point
        self._engine_name = engine_name
        self._bundle_cache_fallback_paths = bundle_cache_fallback_paths or []

    def __repr__(self):
        return "<Resolver: proj id %s, engine %s, entry point %s>" % (
            self._project_id,
            self._engine_name,
            self._entry_point,
        )

    def resolve_configuration(self, config_descriptor, sg_connection):
        """
        Return a configuration object given a config descriptor

        :param config_descriptor: descriptor dict or string
        :param sg_connection: Shotgun API instance
        :return: :class:`Configuration` instance
        """
        log.debug("%s resolving configuration for descriptor %s" % (self, config_descriptor))

        if config_descriptor is None:
            raise TankBootstrapError(
                "No config descriptor specified - Cannot create a configuration object."
            )

        # now probe for a version token in the given descriptor.
        # if that exists, a fixed version workflow will be used where
        # that exact version of the config is used.
        #
        # if a version token is omitted, we request that the latest version
        # should be resolved.
        if isinstance(config_descriptor, str):
            # convert to dict so we can introspect
            config_descriptor = descriptor_uri_to_dict(config_descriptor)

        if "version" in config_descriptor:
            log.debug("Base configuration has a version token defined. "
                      "Will use this fixed version for the bootstrap.")
            resolve_latest = False

        else:
            log.debug("Base configuration descriptor does not have a "
                      "version token defined. Will attempt to determine "
                      "the latest version available.")
            resolve_latest = True

        cfg_descriptor = create_descriptor(
            sg_connection,
            Descriptor.CONFIG,
            config_descriptor,
            fallback_roots=self._bundle_cache_fallback_paths,
            resolve_latest=resolve_latest
        )

        log.debug("Configuration resolved to %r." % cfg_descriptor)

        # first get the cache root
        cache_root = LocalFileStorageManager.get_configuration_root(
            sg_connection.base_url,
            self._project_id,
            self._entry_point,
            None,  # pipeline config id
            LocalFileStorageManager.CACHE
        )

        # resolve the config location both based on entry point and current engine.
        #
        # Example: ~/Library/Caches/Shotgun/mysitename/site.rv_review/cfg
        #
        config_cache_root = os.path.join(cache_root, "cfg")
        filesystem.ensure_folder_exists(config_cache_root)

        log.debug("Configuration root resolved to %s." % config_cache_root)

        # populate current platform, leave rest blank.
        # this resolver only supports local, on-the-fly
        # configurations
        config_root = ShotgunPath.from_current_os_path(config_cache_root)

        # create an object to represent our configuration install
        return Configuration(
            config_root,
            sg_connection,
            cfg_descriptor,
            self._project_id,
            self._entry_point,
            None,  # pipeline config id
            self._bundle_cache_fallback_paths
        )

    def resolve_shotgun_configuration(
        self,
        pipeline_config_name,
        fallback_config_descriptor,
        sg_connection,
        current_login
    ):
        """
        Return a configuration object by requesting a pipeline configuration
        in Shotgun. If no suitable configuration is found, return a configuration
        for the given fallback config.

        :param pipeline_config_name: Name of configuration branch (e.g Primary).
                                     if None, the method will automatically attempt
                                     to resolve the right configuration based on the
                                     current user and the users field on the pipeline
                                     configuration.
        :param fallback_config_descriptor: descriptor dict or string for fallback config.
        :param sg_connection: Shotgun API instance
        :param current_login: The login of the currently logged in user.

        :return: :class:`Configuration` instance
        """
        log.debug(
            "%s resolving configuration from Shotgun Pipeline Configuration %s" % (self, pipeline_config_name)
        )

        fields = [
            "code",
            "users",
            "plugin_ids",
            "sg_plugin_ids",
            "windows_path",
            "linux_path",
            "mac_path",
            "sg_descriptor",
            "descriptor"
        ]

        pipeline_config = None

        if pipeline_config_name is None:
            log.debug("Will auto-detect which pipeline configuration to use.")

            # get the pipeline configs for the current project which are
            # either the primary or is associated with the currently logged in user.
            pipeline_configs = sg_connection.find(
                "PipelineConfiguration",
                [{
                    "filter_operator": "all",
                    "filters": [
                        ["project", "is", {"type": "Project", "id": self._project_id} ],

                        {
                            "filter_operator": "any",
                            "filters": [
                                ["code", "is", constants.PRIMARY_PIPELINE_CONFIG_NAME],
                                ["users.HumanUser.login", "contains", current_login]
                            ]
                        }
                    ]
                }],
                fields,
                order=[{"field_name": "updated_at", "direction": "asc"}]
            )

            log.debug(
                "The following pipeline configurations were found: %s" % pprint.pformat(pipeline_configs)
            )

            # resolve primary and user config
            primary_config = None
            user_config = None
            for pc in pipeline_configs:

                # make sure configuration matches our entry point

                if self.__match_plugin_id(pc.get("plugin_ids")) or self.__match_plugin_id(pc.get("sg_plugin_ids")):
                    # we have a matching pipeline configuration!

                    if pc["code"] == constants.PRIMARY_PIPELINE_CONFIG_NAME:
                        if primary_config:
                            log.warning(
                                "More than one pipeline config detected. Will use the most "
                                "recently updated one."
                            )
                        primary_config = pc
                    else:
                        # user config
                        if user_config:
                            log.warning(
                                "More than one user config detected. Will use the most "
                                "recently updated one."
                            )
                        user_config = pc

            # user pc takes precedence if available.
            pipeline_config = user_config if user_config else primary_config

        else:
            # there is a fixed pipeline configuration name specified.
            log.debug("Will use pipeline configuration '%s'" % pipeline_config_name)

            pipeline_configs = sg_connection.find(
                "PipelineConfiguration",
                [
                    ["project", "is", {"type": "Project", "id": self._project_id} ],
                    ["code", "is", pipeline_config_name],
                ],
                fields,
                order=[{"field_name": "updated_at", "direction": "asc"}]
            )

            log.debug(
                "The following pipeline configurations were found: %s" % pprint.pformat(pipeline_configs)
            )

            for pc in pipeline_configs:

                if self.__match_plugin_id(pc.get("plugin_ids")) or self.__match_plugin_id(pc.get("sg_plugin_ids")):
                    # we have a matching pipeline configuration!

                    if pipeline_config:
                        log.warning(
                            "More than one pipeline config detected. Will use the most "
                            "recently updated one."
                        )
                    pipeline_config = pc

        # now resolve the descriptor to use based on the pipeline config record

        # default to the fallback descriptor
        descriptor = fallback_config_descriptor

        if pipeline_config is None:
            log.debug("No pipeline configuration found. Using fallback descriptor")

        else:
            log.debug(
                "The following pipeline configuration will be used: %s" % pprint.pformat(pipeline_config)
            )

            # now create a descriptor based on the data in the fields.
            # the following priority order exists:
            #
            # 1 windows/linux/mac path
            # 2 descriptor
            # 3 sg_descriptor

            path = ShotgunPath.from_shotgun_dict(pipeline_config)

            if path.current_os:
                log.debug("Descriptor will be based off the path in the pipeline configuration")
                descriptor = {"type": "path", "path": path.current_os}
            elif pipeline_config.get("descriptor"):
                log.debug("Descriptor will be based off the descriptor field in the pipeline configuration")
                descriptor = pipeline_config.get("descriptor")
            elif pipeline_config.get("sg_descriptor"):
                log.debug("Descriptor will be based off the sg_descriptor field in the pipeline configuration")
                descriptor = pipeline_config.get("sg_descriptor")

        log.debug("The descriptor representing the config is %s" % descriptor)

        return self.resolve_configuration(descriptor, sg_connection)

    def __match_plugin_id(self, value):
        """
        Given a plugin id pattern, determine if the current
        plugin id (entry point) matches.

        Patterns can be comma separated and glob style patterns.
        Examples:

            - basic.nuke, basic.maya
            - basic.*, rv_review

        :param value: pattern string to check or None
        :return: True if matching false if not
        """
        if value is None:
            return False

        # first split by comma and strip whitespace
        patterns = [chunk.strip() for chunk in value.split(",")]

        # glob match each item
        for pattern in patterns:
            if fnmatch.fnmatch(self._entry_point, pattern):
                log.debug("Our entry point '%s' matches pattern '%s'" % (self._entry_point, value))
                return True

        return False

