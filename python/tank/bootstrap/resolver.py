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

from ..descriptor import Descriptor, create_descriptor
from .errors import TankBootstrapError
from .configuration import Configuration
from ..util import filesystem
from ..util import ShotgunPath
from ..util import LocalFileStorageManager
from .. import LogManager

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

        # note how we currently always prefer latest as part of the resolve.
        # later on, it will be possible to specify an update policy as part of
        # the descriptor system, allowing a user to specify what latest means -
        # does it actually mean that the version is frozen to a particular version,
        # the latest release on a conservative release track, the latest alpha etc.
        #
        # for installations bundled with manual descriptors, latest currently
        # means the same version that the descriptor is pointing at, so for
        # these installations, version numbers are effectively fixed.
        cfg_descriptor = create_descriptor(
            sg_connection,
            Descriptor.CONFIG,
            config_descriptor,
            fallback_roots=self._bundle_cache_fallback_paths,
            resolve_latest=True
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
        sg_connection
    ):
        """
        Return a configuration object by requesting a pipeline configuration
        in Shotgun. If no suitable configuration is found, return a configuration
        for the given fallback config.

            .. note:: The current implementation for this is a pass-through
                      to the base configuration resolver. In the future, business
                      logic will be added to handle this.

        :param pipeline_config_name: Name of configuration branch (e.g Primary)
        :param fallback_config_descriptor: descriptor dict or string for fallback config.
        :param sg_connection: Shotgun API instance
        :return: :class:`Configuration` instance
        """
        log.debug(
            "%s resolving configuration from Shotgun Pipeline Configuration %s" % (self, pipeline_config_name)
        )

        log.warning(
            "Shotgun pipeline configuration resolve has not been implemented yet. "
            "Falling back on the base configuration resolver."
        )

        # TODO: add shotgun resolve logic
        # - find pipeline config record that matches both
        #   name and entry point
        # - if found, bootstrap into it
        # - if not found, try the fallback

        return self.resolve_configuration(fallback_config_descriptor, sg_connection)

