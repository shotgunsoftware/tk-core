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

import sys
import itertools
import os
import fnmatch
import pprint

from ..descriptor import Descriptor, create_descriptor, descriptor_uri_to_dict
from .errors import TankBootstrapError
from .baked_configuration import BakedConfiguration
from .cached_configuration import CachedConfiguration
from .installed_configuration import InstalledConfiguration
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

    _PIPELINE_CONFIG_FIELDS = [
        "code",
        "project",
        "users",
        "plugin_ids",
        "sg_plugin_ids",
        "windows_path",
        "linux_path",
        "mac_path",
        "sg_descriptor",
        "descriptor"
    ]

    def __init__(
        self,
        plugin_id,
        project_id=None,
        bundle_cache_fallback_paths=None
    ):
        """
        Constructor

        :param plugin_id: The plugin id of the system that is being bootstrapped.
        :param project_id: Project id to create a config object for, None for the site config.
        :param bundle_cache_fallback_paths: Optional list of additional paths where apps are cached.
        """
        self._project_id = project_id
        self._proj_entity_dict = {"type": "Project", "id": self._project_id} if self._project_id else None
        self._plugin_id = plugin_id
        self._bundle_cache_fallback_paths = bundle_cache_fallback_paths or []

    def __repr__(self):
        return "<Resolver: proj id %s, plugin id %s>" % (
            self._project_id,
            self._plugin_id,
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

        # convert to dictionary form
        if isinstance(config_descriptor, str):
            # convert to dict so we can introspect
            config_descriptor = descriptor_uri_to_dict(config_descriptor)

        if config_descriptor["type"] == constants.INSTALLED_DESCRIPTOR_TYPE:

            config_path = os.path.expanduser(os.path.expandvars(config_descriptor["path"]))
            if not os.path.exists(config_path):
                raise TankBootstrapError(
                    "Installed pipeline configuration '%s' does not exist on disk!" % (config_path,)
                )

            # Convert into a ShotgunPath.
            config_path = ShotgunPath.from_current_os_path(config_path)

            # The configuration path here points to the actual pipeline configuration that contains
            # config, cache and install folders.
            return InstalledConfiguration(config_path)

        elif config_descriptor["type"] == constants.BAKED_DESCRIPTOR_TYPE:

            # special case -- this is a full configuration scaffold that
            # has been pre-baked and can be used directly at runtime
            # without having to do lots of copying into temp space.

            baked_config_root = None
            log.debug("Searching for baked config %s" % config_descriptor)
            for root_path in self._bundle_cache_fallback_paths:
                baked_config_path = os.path.join(
                    root_path,
                    constants.BAKED_DESCRIPTOR_FOLDER_NAME,
                    config_descriptor["name"],
                    config_descriptor["version"]
                )
                if os.path.exists(baked_config_path):
                    log.debug("Located baked config in %s" % baked_config_path)
                    # only handle current os platform
                    baked_config_root = ShotgunPath.from_current_os_path(baked_config_path)
                    break

            if baked_config_root is None:
                raise TankBootstrapError("Cannot locate %s!" % config_descriptor)

            # create an object to represent our configuration install
            return BakedConfiguration(
                baked_config_root,
                sg_connection,
                self._project_id,
                self._plugin_id,
                None,  # pipeline config id
                self._bundle_cache_fallback_paths
            )

        else:
            # now probe for a version token in the given descriptor.
            # if that exists, a fixed version workflow will be used where
            # that exact version of the config is used.
            #
            # if a version token is omitted, we request that the latest version
            # should be resolved.
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
                self._plugin_id,
                None,  # pipeline config id
                LocalFileStorageManager.CACHE
            )

            # resolve the config location both based on plugin id and current engine.
            #
            # Example: ~/Library/Caches/Shotgun/mysitename/site.review.rv/cfg
            #
            config_cache_root = os.path.join(cache_root, "cfg")
            filesystem.ensure_folder_exists(config_cache_root)

            log.debug("Configuration root resolved to %s." % config_cache_root)

            # populate current platform, leave rest blank.
            # this resolver only supports local, on-the-fly
            # configurations
            config_root = ShotgunPath.from_current_os_path(config_cache_root)

            # create an object to represent our configuration install
            return CachedConfiguration(
                config_root,
                sg_connection,
                cfg_descriptor,
                self._project_id,
                self._plugin_id,
                None,  # pipeline config id
                self._bundle_cache_fallback_paths
            )

    def _get_unsorted_pipelines_from_shotgun(self, pipeline_config_name, current_login, sg_connection):
        """
        Retrieves pipeline configurations from Shotgun.

        :param str pipeline_config_name: Name of the pipeline configuration requested for. If ``None``,
            all pipeline configurations from the project will be matched.
        :param str current_login: Only retains non-primary configs from the specified user.
        :param ``shotgun_api3.Shotgun`` sg_connection: Connection to the Shotgun site.

        :returns: Iterator over the matching pipeline configurations.
        """
        # get the pipeline configs for the current project which are
        # either the primary or is associated with the currently logged in user.
        # also get the pipeline configs for the site level (project=None)
        log.debug("Requesting pipeline configurations from Shotgun...")

        # If nothing was specified, we need to pick pipelines owned by the user and the primary.
        if pipeline_config_name is None:
            ownership_filters = [
                ["code", "is", constants.PRIMARY_PIPELINE_CONFIG_NAME],
                ["users.HumanUser.login", "is", current_login]
            ]
        elif pipeline_config_name == constants.PRIMARY_PIPELINE_CONFIG_NAME:
            # Only retrieve primary.
            # This makes sense if you don't want sandboxes and specifically want the Primary.
            ownership_filters = [
                ["code", "is", constants.PRIMARY_PIPELINE_CONFIG_NAME]
            ]
        else:
            # If something other than primary was asked for, only get the ones the user owns.
            ownership_filters = [
                ["code", "is", pipeline_config_name],
                ["users.HumanUser.login", "is", current_login]
            ]

        filters = [{
            "filter_operator": "all",
            "filters": [
                {
                    "filter_operator": "any",
                    "filters": [
                        ["project", "is", self._proj_entity_dict],
                        ["project", "is", None],
                    ]
                },
                {
                    "filter_operator": "any",
                    "filters": ownership_filters
                }
            ]
        }]

        log.debug("Retrieving the pipeline configuration list:")
        log.debug(pprint.pformat(filters))

        pipeline_configs = sg_connection.find(
            "PipelineConfiguration",
            filters,
            self._PIPELINE_CONFIG_FIELDS,
            order=[{"field_name": "id", "direction": "asc"}]
        )

        log.debug(
            "The following pipeline configurations were found: %s" % pprint.pformat(pipeline_configs)
        )

        for pc in pipeline_configs:
            # make sure configuration matches our plugin id
            if self._match_plugin_id(pc.get("plugin_ids")) or self._match_plugin_id(pc.get("sg_plugin_ids")):
                path = ShotgunPath.from_shotgun_dict(pc)
                # If a location was specified to get access to that pipeline, return it. Note that we are
                # potentially returning pipeline configurations that have been configured for one platform but
                # not all.
                if pc["descriptor"] or pc["sg_descriptor"] or path:
                    yield pc
                else:
                    log.warning("Pipeline configuration is missing a 'path' or 'descriptor' field: %s" % pc)

    def _sort_pipelines(self, pcs):
        """
        Sorts pipelines into four categories:
            - Project level primary configurations
            - Project level user sandbox configurations
            - Site level primary configurations
            - Site level user sandbox configurations

        :param list pcs: List of pipeline configuration entities with keys `code` and `project`.

        :returns: Four lists of entities. The list are ordered as mentioned above.
        """
        primary_project_configs = []
        user_project_configs = []
        primary_site_configs = []
        user_site_configs = []

        for pc in pcs:
            if self._is_project_pc(pc):
                if self._is_primary_pc(pc):
                    log.debug("Primary match: %s" % pc)
                    primary_project_configs.append(pc)
                else:
                    user_project_configs.append(pc)
                    log.debug("Per-user match: %s" % pc)
            else:
                #
                if self._is_primary_pc(pc):
                    primary_site_configs.append(pc)
                    log.debug("Found primary fallback match: %s" % pc)
                else:
                    user_site_configs.append(pc)
                    log.debug("Found per-user fallback match: %s" % pc)

        return primary_project_configs, user_project_configs, primary_site_configs, user_site_configs

    def _get_sorted_pipeline_configurations(self, pipeline_config_name, current_login, sg_connection):
        """
        Retrieves the pipeline configurations and sorts them into four different categories:
            - Project level primary configurations
            - Project level user sandbox configurations
            - Site level primary configurations
            - Site level user sandbox configurations

        :param str pipeline_config_name: Name of the pipeline configuration requested for. If ``None``,
            all pipeline configurations from the project will be matched.
        :param str current_login: Only retains non-primary configs from the specified user.
        :param ``shotgun_api3.Shotgun`` sg_connection: Connection to the Shotgun site.

        :returns: Four lists of entities. The list are ordered as mentioned above.

        """
        pcs = self._get_unsorted_pipelines_from_shotgun(pipeline_config_name, current_login, sg_connection)
        # Sort all the pipeline configurations in their respective bucket.
        return self._sort_pipelines(pcs)

    def find_matching_pipeline_configurations(self, pipeline_config_name, current_login, sg_connection):
        """
        Finds all the pipelines matching the query parameters.

        :param str pipeline_config_name: Name of the pipeline configuration requested for. If ``None``,
            all pipeline configurations from the project will be matched.
        :param str current_login: Only retains non-primary configs from the specified user.
        :param ``shotgun_api3.Shotgun`` sg_connection: Connection to the Shotgun site.

        :returns: Iterator over the matching pipeline configurations.
        """

        # Get all the pipeline configurations, each sorted in their right category.
        (primary_project_configs,
         user_project_configs,
         primary_site_configs,
         user_site_configs) = self._get_sorted_pipeline_configurations(
            pipeline_config_name, current_login, sg_connection
        )

        # If there is a primary project configuration, then we don't want to use site configurations
        # on this project.
        if primary_project_configs:
            primary_site_configs = []

        return itertools.chain(user_project_configs, primary_project_configs, user_site_configs, primary_site_configs)

    def _is_primary_pc(self, pc):
        """
        Tests if a pipeline configuration is a sandbox.

        :param pc: Pipeline configuration entity.

        :returns: True if pipeline configuration is a primary, False otherwise.
        """
        return pc["code"] == constants.PRIMARY_PIPELINE_CONFIG_NAME

    def _is_project_pc(self, pc):
        """
        Tests if a pipeline configuration is attached to a project.

        :param pc: Pipeline configuration entity.

        :returns: True if the pipeline configuration is attached to a project, False otherwise.
        """
        return pc["project"] is not None

    def resolve_shotgun_configuration(
        self,
        pipeline_config_identifier,
        fallback_config_descriptor,
        sg_connection,
        current_login
    ):
        """
        Return a configuration object by requesting a pipeline configuration
        in Shotgun. If no suitable configuration is found, return a configuration
        for the given fallback config.

        :param pipeline_config_identifier: Name or id of configuration branch (e.g Primary).
                                           If None, the method will automatically attempt
                                           to resolve the right configuration based on the
                                           current user and the users field on the pipeline
                                           configuration.
        :param fallback_config_descriptor: descriptor dict or string for fallback config.
        :param sg_connection: Shotgun API instance
        :param current_login: The login of the currently logged in user.

        :return: :class:`Configuration` instance
        """
        log.debug(
            "%s resolving configuration from Shotgun Pipeline Configuration %s" % (self, pipeline_config_identifier)
        )

        pipeline_config = None

        if not isinstance(pipeline_config_identifier, int):
            log.debug("Will auto-detect which pipeline configuration to use.")

            # Get all the pipeline configurations that can be used given our project
            # restriction.
            pcs = self._get_unsorted_pipelines_from_shotgun(
                pipeline_config_identifier, current_login, sg_connection
            )

            # Sort all the pipeline configurations in their respective bucket.
            (primary_project_configs, user_project_configs,
             primary_site_configs, user_site_configs) = self._sort_pipelines(pcs)

            # Now select in order of priority. Note that the last pipeline encountered in the
            # a any given level is the one we will use.
            if user_project_configs:
                # A per-user pipeline config for the current project has top priority
                pipeline_config = user_project_configs[0]

            elif primary_project_configs:
                # if there is a primary config for our current project, this takes precedence
                pipeline_config = primary_project_configs[0]

            elif user_site_configs:
                # if there is a pipeline config for our current user with project field None
                # that takes precedence
                pipeline_config = user_site_configs[0]

            elif primary_site_configs:
                # Lowest priority - A Primary pipeline configuration with project field None
                pipeline_config = primary_site_configs[0]

            else:
                # we may not have any pipeline configuration matches at all:
                pipeline_config = None
        else:
            log.debug("Will use pipeline configuration id '%s'" % pipeline_config_identifier)

            log.debug("Requesting pipeline configuration data from Shotgun...")

            # Fetch the one and only config that matches this id.
            pipeline_config = sg_connection.find_one(
                "PipelineConfiguration",
                [
                    ["id", "is", pipeline_config_identifier],
                ],
                self._PIPELINE_CONFIG_FIELDS
            )

            # If it doesn't exist, we're in trouble.
            if pipeline_config is None:
                raise TankBootstrapError(
                    "Pipeline configuration with id '%d' doesn't exist for project id '%d' in Shotgun." %
                    (pipeline_config_identifier, self._proj_entity_dict["id"])
                )

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

            if path and not path.current_os:
                log.debug(
                    "No path set for %s on the Pipeline Configuration \"%s\" (id %d).",
                    sys.platform,
                    pipeline_config["code"],
                    pipeline_config["id"]
                )
                raise TankBootstrapError("The Toolkit configuration path has not\n"
                                         "been set for your operating system.")
            elif path:
                # Emit a warning when both the OS field and descriptor field is set.
                if pipeline_config.get("descriptor") or pipeline_config.get("sg_descriptor"):
                    log.warning("Fields for path based and descriptor based pipeline configuration are both set. "
                                "Using path based field.")

                log.debug("Descriptor will be based off the path in the pipeline configuration")
                descriptor = {"type": constants.INSTALLED_DESCRIPTOR_TYPE, "path": path.current_os}
            elif pipeline_config.get("descriptor"):
                # Emit a warning when the sg_descriptor is set as well.
                if pipeline_config.get("sg_descriptor"):
                    log.warning("Both sg_descriptor and descriptor fields are set. Using descriptor field.")

                log.debug("Descriptor will be based off the descriptor field in the pipeline configuration")
                descriptor = pipeline_config.get("descriptor")
            elif pipeline_config.get("sg_descriptor"):
                log.debug("Descriptor will be based off the sg_descriptor field in the pipeline configuration")
                descriptor = pipeline_config.get("sg_descriptor")

        log.debug("The descriptor representing the config is %s" % descriptor)

        return self.resolve_configuration(descriptor, sg_connection)

    def _match_plugin_id(self, value):
        """
        Given a plugin id pattern, determine if the current
        plugin id matches.

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
            if fnmatch.fnmatch(self._plugin_id, pattern):
                log.debug("Our plugin id '%s' matches pattern '%s'" % (self._plugin_id, value))
                return True

        return False
