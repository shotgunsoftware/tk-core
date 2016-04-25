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
import logging

from ..descriptor import Descriptor, create_descriptor
from .errors import TankBootstrapError
from .configuration import Configuration
from ..util import filesystem
from ..util import ShotgunPath
from ..paths import PathManager

log = logging.getLogger(__name__)

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
            raise TankBootstrapError(
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
        cache_root = PathManager.get_configuration_root(
            self._sg_connection.base_url,
            project_id,
            None,  # pipeline config id
            PathManager.CACHE
        )

        # now locate configs created by the base config resolver
        # in cfg/base/engine-name folder
        config_cache_root = os.path.join(
            cache_root,
            "cfg.base",
            filesystem.create_valid_filename(engine_name)
        )
        filesystem.ensure_folder_exists(config_cache_root)

        # populate current platform, leave rest blank.
        # this resolver only supports local, on-the-fly
        # configurations
        config_root = ShotgunPath.from_current_os_path(config_cache_root)

        # create an object to represent our configuration install
        return Configuration(
            config_root,
            self._sg_connection,
            cfg_descriptor,
            project_id,
            None,  # pipeline config id
            self._bundle_cache_fallback_paths
        )


