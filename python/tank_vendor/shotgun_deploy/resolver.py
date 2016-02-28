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
import os

from . import util
from . import Descriptor, create_descriptor
from . import constants
from .errors import ShotgunDeployError
from .. import shotgun_api3
from ..shotgun_base import get_shotgun_storage_key

from .configuration import create_managed_configuration, create_unmanaged_configuration



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
        namespace,
        base_config_location
    ):
        """
        Given a Shotgun project (or None for site mode), return a configuration
        object based on a particular set of resolution logic rules.

        This method needs to be subclassed by different methods, implementing different
        business logic for resolve. This resolve may include different type of fallback
        schemes, simple non-shotgun schemes etc.

        :param project_id: Project id to create a config object for, None for the site config.
        :param pipeline_config_name: Name of configuration branch (e.g Primary)
        :param namespace: Config namespace to distinguish it from other configs with the
                          same project id and pipeline configuration name.
        :param base_config_location: Location dict or string for fallback config.
        :return: Configuration instance
        """
        raise NotImplementedError


class BasicConfigurationResolver(ConfigurationResolver):
    """
    Basic configuration resolves which implements the logic
    toolkit is using today.
    """

    def __init__(self, sg_connection, bundle_cache_fallback_paths):
        """
        Constructor

        :param sg_connection: Shotgun API instance
        :param bundle_cache_fallback_paths: List of additional paths where apps are cached.
        """
        super(BasicConfigurationResolver, self).__init__(
            sg_connection,
            bundle_cache_fallback_paths
        )

    def resolve_configuration(
        self,
        project_id,
        pipeline_config_name,
        namespace,
        base_config_location
    ):
        """
        Given a Shotgun project (or None for site mode), return a configuration
        object based on a particular set of resolution logic rules.

        :param project_id: Project id to create a config object for, None for the site config.
        :param pipeline_config_name: Name of configuration branch (e.g Primary)
        :param namespace: Config namespace to distinguish it from other configs with the
                          same project id and pipeline configuration name.
        :param base_config_location: Location dict or string for fallback config.
        :return: Configuration instance
        """
        if project_id:
            return self._resolve_project_configuration(project_id, pipeline_config_name, namespace, base_config_location)
        else:
            return self._resolve_site_configuration(namespace, base_config_location)

    def _resolve_site_configuration(self, namespace, base_config_location):
        """
        Return a configuration object for the site config, based on a particular
        set of resolution logic rules.

        :param namespace: Config namespace to distinguish it from other configs with the
                          same project id and pipeline configuration name.
        :param base_config_location: Location dict or string for fallback config.
        :return: Configuration instance
        """

        # The following is to provide backwards compatibility with the
        # previous versions of the Shotgun Desktop which used a
        # pipeline configuration without any project or a pipeline
        # configuration attached to the site config.
        # If we have a site configuration and one of it's path is set, then
        # we have a managed pipeline configuration.
        pc = self._find_site_pipeline_configuration_entity()
        if pc and (pc["mac_path"] or pc["windows_path"] or pc["linux_path"]):
            log.debug("Legacy site configuration is managed.")
            is_managed = True
        else:
            is_managed = False

        if is_managed:
            return create_managed_configuration(
                self._sg_connection,
                pc.get("project.Project.id", None),
                pc.get("id"),
                namespace,
                self._bundle_cache_fallback_paths,
                True,
                pc.get("windows_path"),
                pc.get("linux_path"),
                pc.get("mac_path")
            )
        else:
            return self._create_base_configuration(
                None,
                base_config_location,
                namespace
            )

    def _resolve_project_configuration(self, project_id, pipeline_config_name, namespace, base_config_location):
        """
        Given a Shotgun project, return a configuration object based on a particular
        set of resolution logic rules.

        :param project_id: Project id to create a config object for, None for the site config.
        :param pipeline_config_name: Name of configuration branch (e.g Primary)
        :param namespace: Config namespace to distinguish it from other configs with the
                          same project id and pipeline configuration name.
        :param base_config_location: Location dict or string for fallback config.
        :return: Configuration instance
        """

        # now resolve pipeline config details
        project_entity = {"type": "Project", "id": project_id}

        # find a pipeline configuration in Shotgun.
        log.debug("Checking pipeline configuration in Shotgun...")
        pc_data = self._sg_connection.find_one(
            constants.PIPELINE_CONFIGURATION_ENTITY_TYPE,
            [["code", "is", pipeline_config_name],
             ["project", "is", project_entity]],
            ["mac_path",
             "windows_path",
             "linux_path",
             constants.SHOTGUN_PIPELINECONFIG_URI_FIELD]
        )
        log.debug("Shotgun returned: %s" % pc_data)

        if pc_data:

            if pc_data.get(get_shotgun_storage_key()):
                # we have paths specified for the local platform!
                return create_managed_configuration(
                    self._sg_connection,
                    project_id,
                    pc_data.get("id"),
                    namespace,
                    self._bundle_cache_fallback_paths,
                    True,
                    pc_data.get("windows_path"),
                    pc_data.get("linux_path"),
                    pc_data.get("mac_path")
                )

            elif pc_data.get(constants.SHOTGUN_PIPELINECONFIG_URI_FIELD):
                uri = pc_data.get(constants.SHOTGUN_PIPELINECONFIG_URI_FIELD)
                log.debug("Attempting to resolve config uri %s" % uri)

                cfg_descriptor = create_descriptor(
                    self._sg_connection,
                    Descriptor.CONFIG,
                    uri,
                    fallback_roots=self._bundle_cache_fallback_paths
                )

                return create_unmanaged_configuration(
                    self._sg_connection,
                    cfg_descriptor,
                    project_id,
                    pc_data.get("id"),
                    namespace,
                    self._bundle_cache_fallback_paths
                )

        # fall back on base
        if base_config_location is None:
            raise ShotgunDeployError(
                "No base configuration specified and no pipeline "
                "configuration exists in Shotgun for the given project. "
                "Cannot create a configuration object.")

        return self._create_base_configuration(
            project_id,
            base_config_location,
            namespace
        )

    def _create_base_configuration(self, project_id, base_config_location, namespace):
        """
        Helper method that creates a config wrapper object
        from the base configuration locator.

        :param project_id: Shotgun project id
        :param base_config_location: Location dict or string for fallback config.
        :param namespace: Config namespace to distinguish it from other configs with the
                          same project id and pipeline configuration name.
        :return: Configuration instance
        """
        cfg_descriptor = create_descriptor(
            self._sg_connection,
            Descriptor.CONFIG,
            base_config_location,
            fallback_roots=self._bundle_cache_fallback_paths
        )

        log.debug("Creating a configuration wrapper based on %r." % cfg_descriptor)

        # create an object to represent our configuration install
        return create_unmanaged_configuration(
            self._sg_connection,
            cfg_descriptor,
            project_id,
            None, # pipeline config id
            namespace,
            self._bundle_cache_fallback_paths
        )

    def _find_site_pipeline_configuration_entity(self):
        """
        Look for the site pipeline configuration entity associated with the site
        config.

        Clients who have been using Shotgun Desktop in the past actually have
        a pipeline configurarions in Shotgun for their site config.

        :returns: The pipeline configuration entity for the site config, if it
            exists.
        """
        # interesting fields to return
        fields = ["id", "code", "windows_path", "mac_path", "linux_path", "project"]

        # Find the right pipeline configuration. We'll always pick a projectless
        # one over one with the Template Project. To have a deterministic behaviour,
        # we'll also always sort the ids. Common sense would dictate that the
        # sorting needs to be done from low ids to high ids. However, entries with
        # no project get systematically pushed to the end of the list, no matter
        # the ordering. Since we want to pick the projectless configuration first,
        # we'll reverse the sorting order on ids so the last returned result is the
        # lowest projectless configuration (if available). If no projectless
        # pipeline configurations are available, then the ones from the Template
        # project will show up. Once again, because we are sorting configurations
        # based on decreasing ids, the last entry is still the one with the lowest
        # id.

        try:
            pcs = self._sg_connection.find(
                "PipelineConfiguration",
                [{
                    "filter_operator": "any",
                    "filters": [
                        ["project", "is", None],
                        {
                            "filter_operator": "all",
                            "filters": [
                                ["project.Project.name", "is", "Template Project"],
                                ["project.Project.layout_project", "is", None]
                            ]
                        }
                    ]
                }],
                fields=fields,
                order=[
                    # Sorting on the project id doesn't actually matter. We want
                    # some sorting simply because this will force grouping between
                    # configurations with a project and those that don't.
                    {'field_name':'project.Project.id','direction':'asc'},
                    {'field_name':'id','direction':'desc'}
                ]
        )
        except shotgun_api3.shotgun.Fault:
            # In case where Toolkit is not enabled for a site, the
            # 'PipelineConfiguration' entity will not exist, and this exception
            # will be raised. Continue as if no entities were returned
            pcs = []


        if len(pcs) == 0:
            log.debug("No legacy site pipeline configuration found.")
            return None

        log.debug("Legacy site pipeline configuration found.")

        # Pick the last result. See the big comment before the Shotgun query to understand.
        pc = pcs[-1]
        # It is possible to get multiple pipeline configurations due to user error.
        # Log a warning if there was more than one pipeline configuration found.
        if len(pcs) > 1:
            log.info(
                "More than one pipeline configuration was found (%s), using %d" %
                (", ".join([str(p["id"]) for p in pcs]), pc["id"])
            )

        return pc

    def _get_platform_field_name(self):
        """
        Return the name of the Project field for the path for the current
        platform.

        :returns: Field with the path for the current platform.
        """
        # find what path field from the entity we need
        if sys.platform == "darwin":
            return "mac_path"
        elif sys.platform == "win32":
            return "windows_path"
        elif sys.platform.startswith("linux"):
            return "linux_path"
        else:
            raise RuntimeError("unknown platform: %s" % sys.platform)

    # FIXME: Not invoking this method until we can discuss with Rob if
    # this is still a valid
    def _update_legacy_site_config_root(self, pc):
        """
        Honor the TK_SITE_CONFIG_ROOT environment variable for managed
        site configs from Shotgun Desktop.

        :param pc: Pipeline configuration that needs to use another path

        """
        env_site = os.environ.get("TK_SITE_CONFIG_ROOT")
        if env_site:
            log.info(
                "$TK_SITE_CONFIG_ROOT site config override found, using "
                "site config path '%s' when launching desktop." % str(env_site)
            )
            if sys.platform in ["darwin", "linux"]:
                env_site = os.path.expanduser(str(env_site))

            # Patch the site config root.
            pc[self._get_platform_field_name()] = env_site
