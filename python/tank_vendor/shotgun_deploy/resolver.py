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
import sys
from . import util
from . import Descriptor, create_descriptor
from . import constants
from . import paths
from .errors import ShotgunDeployError
from ..shotgun_base import get_shotgun_storage_key
from .. import shotgun_base

from .configuration import Configuration

log = util.get_shotgun_deploy_logger()


class ConfigurationResolver(object):
    """
    Base class for defining recipes for how to resolve a configuration object
    given a particular project and configuration.
    """

    def __init__(self, sg_connection, bundle_cache_fallback_paths):
        """
        Constructor.

        :param sg_connection: Shotgun API instance
        :param bundle_cache_fallback_paths: List of additional paths where apps are cached.
        """
        self._sg_connection = sg_connection
        self._bundle_cache_fallback_paths = bundle_cache_fallback_paths

    def resolve_configuration(
        self,
        project_id,
        pipeline_config_name,
        engine_name,
        base_config_descriptor,
        get_latest_config
    ):
        """
        Given a Shotgun project (or None for site mode), return a configuration
        object based on a particular set of resolution logic rules.

        This method needs to be subclassed by different methods, implementing different
        business logic for resolve. This resolve may include different type of fallback
        schemes, simple non-shotgun schemes etc.

        :param project_id: Project id to create a config object for, None for the site config.
        :param pipeline_config_name: Name of configuration branch (e.g Primary)
        :param engine_name: Engine name for which we are resolving the configuration.
        :param base_config_descriptor: descriptor dict or string for fallback config.
        :param get_latest_config: Flag to indicate that latest version of the fallback config
                                  should be resolved and used.
        :return: Configuration instance
        """
        raise NotImplementedError


class BaseConfigurationResolver(ConfigurationResolver):
    """
    An simplistic resolver which is not aware of pipeline configurations
    in Shotgun. This will always resolve the base config location
    regardless of any external state.
    """

    def __init__(self, sg_connection, bundle_cache_fallback_paths):
        """
        Constructor

        :param sg_connection: Shotgun API instance
        :param bundle_cache_fallback_paths: List of additional paths where apps are cached.
        """
        super(BaseConfigurationResolver, self).__init__(
            sg_connection,
            bundle_cache_fallback_paths
        )

    def resolve_configuration(
        self,
        project_id,
        pipeline_config_name,
        engine_name,
        base_config_descriptor,
        get_latest_config
    ):
        """
        Given a Shotgun project (or None for site mode), return a configuration
        object based on a particular set of resolution logic rules.

        The BaseConfigurationResolver is a simple and fast implementation
        which does not take pipeline configuration entities in Shotgun into account.
        It just returns the base configuration.

        Note: This implementation is expected to be replaced with the
              BasicConfigurationResolver at some point soon.

        :param project_id: Project id to create a config object for, None for the site config.
        :param pipeline_config_name: Name of configuration branch (e.g Primary)
        :param engine_name: Engine name for which we are resolving the configuration.
        :param base_config_descriptor: descriptor dict or string for fallback config.
        :param get_latest_config: Flag to indicate that latest version of the fallback config
                                  should be resolved and used.
        :return: Configuration instance
        """
        log.debug(
            "%s resolving a configuration for project %s, "
            "pipeline config %s, engine %s" % (
                self,
                project_id,
                pipeline_config_name,
                engine_name
            )
        )

        # fall back on base
        if base_config_descriptor is None:
            raise ShotgunDeployError(
                "No base configuration specified and no pipeline "
                "configuration exists in Shotgun for the given project. "
                "Cannot create a configuration object.")

        cfg_descriptor = create_descriptor(
            self._sg_connection,
            Descriptor.CONFIG,
            base_config_descriptor,
            fallback_roots=self._bundle_cache_fallback_paths,
            resolve_latest=get_latest_config
        )

        log.debug("Configuration resolved to %r." % cfg_descriptor)

        # now determine the location of the configuration
        config_root = {"win32": None, "linux2": None, "darwin": None}

        # first get the cache root
        cache_root = shotgun_base.get_pipeline_config_cache_root(
            self._sg_connection.base_url,
            project_id,
            pipeline_configuration_id=None
        )

        # now locate configs created by the base config resolver
        # in cfg/base/engine-name folder
        config_cache_root = os.path.join(
            cache_root,
            "cfg",
            "base",
            util.create_valid_filename(engine_name)
        )
        shotgun_base.ensure_folder_exists(config_cache_root)

        # populate current platform, leave rest blank.
        # this resolver only supports local, on-the-fly
        # configurations
        config_root[sys.platform] = config_cache_root

        # create an object to represent our configuration install
        return Configuration(
            config_root,
            self._sg_connection,
            cfg_descriptor,
            project_id,
            None,  # pipeline config id
            self._bundle_cache_fallback_paths
        )


# class DefaultShotgunConfigurationResolver(ConfigurationResolver):
#     """
#     Default Shotgun config resolver which implements the logic
#     toolkit is using today. It first tries to find a Pipeline Configuration
#     in Shotgun, if this fails, it falls back on the base configuration.
#
#     This allows for a workflow where a project can start its life tracking
#     against a fully remote config - say the default config in the app store -
#     and when the time comes where the project needs to be customized, a
#     pipeline configuration is created in Shotgun. Once this is created, it
#     takes precedence over the base config location. The old path fields
#     on pipeline configuration are checked first and take precedence over
#     anything else. Secondly it looks for a config str field on the pipeline
#     configuration and tries to interpret and resolve this as a descriptor uri.
#     configuration and tries to interpret and resolve this as a descriptor uri.
#
#     @todo - handle namespace support in shotgun/pipeline config fields
#     @todo - finalize constants.SHOTGUN_PIPELINECONFIG_URI_FIELD
#     """
#
#     def __init__(self, sg_connection, bundle_cache_fallback_paths):
#         """
#         Constructor
#
#         :param sg_connection: Shotgun API instance
#         :param bundle_cache_fallback_paths: List of additional paths where apps are cached.
#         """
#         super(DefaultShotgunConfigurationResolver, self).__init__(
#             sg_connection,
#             bundle_cache_fallback_paths
#         )
#
#     def resolve_configuration(
#         self,
#         project_id,
#         pipeline_config_name,
#         namespace,
#         base_config_descriptor,
#         get_latest_config
#     ):
#         """
#         Given a Shotgun project (or None for site mode), return a configuration
#         object based on a particular set of resolution logic rules.
#
#         :param project_id: Project id to create a config object for, None for the site config.
#         :param pipeline_config_name: Name of configuration branch (e.g Primary)
#         :param namespace: Config namespace to distinguish it from other configs with the
#                           same project id and pipeline configuration name.
#         :param base_config_descriptor: descriptor dict or string for fallback config.
#         :param get_latest_config: Flag to indicate that latest version of the fallback config
#                           should be resolved and used.
#         :return: Configuration instance
#         """
#
#         log.debug(
#             "%s resolving a configuration for project %s, "
#             "pipeline config %s, namespace %s" % (
#                 self,
#                 project_id,
#                 pipeline_config_name,
#                 namespace
#             )
#         )
#
#         # first attempt to resolve in Shotgun
#         config = self._resolve_sg_configuration(
#             project_id,
#             pipeline_config_name,
#             namespace
#         )
#
#         # if that fails, fall back onto our base config
#         if config is None:
#             log.debug(
#                 "Could not resolve a config from Shotgun, "
#                 "falling back on base config.")
#             config = self._create_base_configuration(
#                 project_id,
#                 base_config_descriptor,
#                 get_latest_config,
#                 namespace
#             )
#
#         return config
#
#     def _resolve_sg_configuration(self, project_id, pipeline_config_name, namespace):
#         """
#         Returns a configuration object representing a project pipeline config in Shotgun.
#
#         If no config can be resolved in Shotgun, None is returned.
#
#         @todo - handle namespace support
#
#         :param project_id: Project id to create a config object for
#         :param pipeline_config_name: Name of configuration branch (e.g Primary)
#         :param namespace: Config namespace to distinguish it from other configs with the
#                           same project id and pipeline configuration name.
#         :return: Configuration instance or None if nothing found in Shotgun
#         """
#         if not util.is_toolkit_activated_in_shotgun(self._sg_connection):
#             # In case where Toolkit is not enabled for a site, the
#             # 'PipelineConfiguration' entity will not exist
#             return None
#
#         # find a pipeline configuration in Shotgun.
#         log.debug("Looking for a pipeline configuration in Shotgun...")
#
#         if project_id is None:
#
#             # attempt to resolve a site configuration!
#
#             # The following is to provide backwards compatibility with the
#             # previous versions of the Shotgun Desktop which used a
#             # pipeline config with blank paths to denote an 'auto-updating'
#             # config.
#             #
#             # this pipeline config was the either associated with the
#             # template project (old versions of desktop) or have its
#             # project field set to None (this is how a site configuration
#             # is handled today).
#
#             # get the right site pipeline config record or None if not found
#             pc_data = self._find_site_pipeline_configuration_entity(
#                 pipeline_config_name,
#                 namespace
#             )
#
#         else:
#
#             # attempt to resolve a project configuration
#             # now resolve pipeline config details
#             project_entity = {"type": "Project", "id": project_id}
#
#             pc_data = self._sg_connection.find_one(
#                 constants.PIPELINE_CONFIGURATION_ENTITY_TYPE,
#                 [["code", "is", pipeline_config_name],
#                  ["project", "is", project_entity]],
#                 ["mac_path",
#                  "windows_path",
#                  "linux_path",
#                  constants.SHOTGUN_PIPELINECONFIG_URI_FIELD]
#             )
#
#         log.debug("...Shotgun returned: %s" % pc_data)
#
#         if pc_data:
#
#             if pc_data.get(get_shotgun_storage_key()):
#                 # we have paths specified for the local platform!
#                 return create_installed_configuration(
#                     self._sg_connection,
#                     project_id,
#                     pc_data.get("id"),
#                     namespace,
#                     self._bundle_cache_fallback_paths,
#                     True,
#                     pc_data.get("windows_path"),
#                     pc_data.get("linux_path"),
#                     pc_data.get("mac_path")
#                 )
#
#             elif pc_data.get(constants.SHOTGUN_PIPELINECONFIG_URI_FIELD):
#                 uri = pc_data.get(constants.SHOTGUN_PIPELINECONFIG_URI_FIELD)
#                 log.debug("Attempting to resolve config uri %s" % uri)
#
#                 cfg_descriptor = create_descriptor(
#                     self._sg_connection,
#                     Descriptor.CONFIG,
#                     uri,
#                     fallback_roots=self._bundle_cache_fallback_paths
#                 )
#
#                 return create_automatic_configuration(
#                     self._sg_connection,
#                     cfg_descriptor,
#                     project_id,
#                     pc_data.get("id"),
#                     namespace,
#                     self._bundle_cache_fallback_paths
#                 )
#
#         # no luck resolving from Shotgun
#         return None
#
#     def _create_base_configuration(self, project_id, base_config_descriptor, get_latest_config, namespace):
#         """
#         Helper method that creates a config wrapper object
#         from the base configuration descriptor.
#
#         :param project_id: Shotgun project id
#         :param base_config_descriptor: descriptor dict or string for fallback config.
#         :param get_latest_config: Flag to indicate that latest version of the fallback config
#                           should be resolved and used.
#         :param namespace: Config namespace to distinguish it from other configs with the
#                           same project id and pipeline configuration name.
#         :return: Configuration instance
#         """
#         # fall back on base
#         if base_config_descriptor is None:
#             raise ShotgunDeployError(
#                 "No base configuration specified and no pipeline "
#                 "configuration exists in Shotgun for the given project. "
#                 "Cannot create a configuration object.")
#
#         cfg_descriptor = create_descriptor(
#             self._sg_connection,
#             Descriptor.CONFIG,
#             base_config_descriptor,
#             fallback_roots=self._bundle_cache_fallback_paths,
#             resolve_latest=get_latest_config
#         )
#
#         log.debug("Creating a configuration wrapper based on %r." % cfg_descriptor)
#
#         # create an object to represent our configuration install
#         return create_automatic_configuration(
#             self._sg_connection,
#             cfg_descriptor,
#             project_id,
#             None, # pipeline config id
#             namespace,
#             self._bundle_cache_fallback_paths
#         )
#
#     def _find_site_pipeline_configuration_entity(self, pipeline_config_name, namespace):
#         """
#         Look for the site pipeline configuration entity associated with the site
#         config.
#
#         Clients who have been using Shotgun Desktop in the past actually have
#         a pipeline configurarions in Shotgun for their site config.
#
#         # @todo - handle namespace parameter
#
#         :param pipeline_config_name: Name of configuration branch (e.g Primary)
#         :param namespace: Config namespace to distinguish it from other configs with the
#                           same project id and pipeline configuration name.
#         :returns: The pipeline configuration entity for the site config, if it
#                   exists.
#         """
#
#         # interesting fields to return
#         fields = ["id", "code", "windows_path", "mac_path", "linux_path", "project"]
#
#         # Find the right pipeline configuration. We'll always pick a projectless
#         # one over one with the Template Project. To have a deterministic behaviour,
#         # we'll also always sort the ids. Common sense would dictate that the
#         # sorting needs to be done from low ids to high ids. However, entries with
#         # no project get systematically pushed to the end of the list, no matter
#         # the ordering. Since we want to pick the projectless configuration first,
#         # we'll reverse the sorting order on ids so the last returned result is the
#         # lowest projectless configuration (if available). If no projectless
#         # pipeline configurations are available, then the ones from the Template
#         # project will show up. Once again, because we are sorting configurations
#         # based on decreasing ids, the last entry is still the one with the lowest
#         # id.
#
#         pcs = self._sg_connection.find(
#             constants.PIPELINE_CONFIGURATION_ENTITY_TYPE,
#             [{
#                 "filter_operator": "any",
#                 "filters": [
#                     {
#                         # either look for a pipeline config with project None
#                         # and the given name (e.g. Primary)
#                         "filter_operator": "all",
#                         "filters": [
#                             ["project", "is", None],
#                             ["code", "is", pipeline_config_name]
#                         ]
#                     },
#                     {
#                         # ...or look for the template project for legacy cases
#                         "filter_operator": "all",
#                         "filters": [
#                             ["project", "is", None],
#                             ["project.Project.name", "is", "Template Project"],
#                             ["project.Project.layout_project", "is", None]
#                         ]
#                     }
#                 ]
#             }],
#             fields=fields,
#             order=[
#                 # Sorting on the project id doesn't actually matter. We want
#                 # some sorting simply because this will force grouping between
#                 # configurations with a project and those that don't.
#                 {"field_name": "project.Project.id", "direction": "asc"},
#                 {"field_name": "id", "direction": "desc"}
#             ]
#         )
#
#         if len(pcs) == 0:
#             log.debug("No site pipeline configuration found.")
#             return None
#
#         log.debug("Site pipeline configuration found.")
#
#         # Pick the last result. See the big comment before the Shotgun query to understand.
#         pc = pcs[-1]
#         # It is possible to get multiple pipeline configurations due to user error.
#         # Log a warning if there was more than one pipeline configuration found.
#         if len(pcs) > 1:
#             log.warning(
#                 "More than one site pipeline configuration was found (%s), using %d" %
#                 (", ".join([str(p["id"]) for p in pcs]), pc["id"])
#             )
#
#         return pc
#
#     # # todo: Not invoking this method until we can discuss with Rob if
#     # # this is still a valid parameter.
#     # def _update_legacy_site_config_root(self, pc):
#     #     """
#     #     Honor the TK_SITE_CONFIG_ROOT environment variable for
#     #     site configs from Shotgun Desktop.
#     #
#     #     :param pc: Pipeline configuration that needs to use another path
#     #
#     #     """
#     #     env_site = os.environ.get("TK_SITE_CONFIG_ROOT")
#     #     if env_site:
#     #         log.info(
#     #             "$TK_SITE_CONFIG_ROOT site config override found, using "
#     #             "site config path '%s' when launching desktop." % str(env_site)
#     #         )
#     #         if sys.platform in ["darwin", "linux"]:
#     #             env_site = os.path.expanduser(str(env_site))
#     #
#     #         # Patch the site config root.
#     #         pc[get_shotgun_storage_key()] = env_site
