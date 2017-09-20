# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

from .configuration import Configuration
from .configuration_writer import ConfigurationWriter

from .. import LogManager
from .. import constants
import cPickle as pickle

from ..util import ShotgunPath

log = LogManager.get_logger(__name__)


class BakedConfiguration(Configuration):
    """
    Represents a configuration that has been baked out at build time,
    containing incomplete state data - at bake time we don't yet know
    what project id, what site, configuration id etc. will be required.
    """

    def __init__(
            self,
            path,
            sg,
            project_id,
            plugin_id,
            pipeline_config_id,
            bundle_cache_fallback_paths,
            descriptor
    ):
        """
        Constructor.

        :param path: ShotgunPath object describing the path to this configuration
        :param sg: Shotgun API instance
        :param project_id: Project id for the shotgun project associated with the
                           configuration. For a site-level configuration, this
                           can be set to None.
        :param plugin_id: Plugin id string to identify the scope for a particular plugin
                          or integration. For more information,
                          see :meth:`~sgtk.bootstrap.ToolkitManager.plugin_id`. For
                          non-plugin based toolkit projects, this value is None.
        :param pipeline_config_id: Pipeline Configuration id for the shotgun
                                   pipeline config id associated. If a config does
                                   not have an associated entity in Shotgun, this
                                   should be set to None.
        :param bundle_cache_fallback_paths: List of additional paths where apps are cached.
        :param descriptor: ConfigDescriptor for the associated config
        """
        super(BakedConfiguration, self).__init__(path, descriptor)
        self._path = path
        self._sg_connection = sg
        self._project_id = project_id
        self._plugin_id = plugin_id
        self._pipeline_config_id = pipeline_config_id
        self._bundle_cache_fallback_paths = bundle_cache_fallback_paths

    def __str__(self):
        """
        User friendly representation of the config
        """
        return "Pre-baked config '%s'" % self._path

    def __repr__(self):
        """
        Low level representation of the config.
        """
        return "<Pre-baked config '%s'>" % self._path

    def status(self):
        """
        Compares the actual configuration installed on disk against the
        associated configuration described by the descriptor passed in via
        the class constructor.

        :returns: LOCAL_CFG_UP_TO_DATE, LOCAL_CFG_MISSING,
                  LOCAL_CFG_DIFFERENT, or LOCAL_CFG_INVALID
        """
        return self.LOCAL_CFG_UP_TO_DATE

    def update_configuration(self):
        """
        Ensure that the configuration is up to date with the one
        given by the associated descriptor.

        In the case of a baked configuration everything has been
        baked into a static setup at build time so this method
        does not do anything.
        """
        pass

    def get_tk_instance(self, sg_user):
        """
        Returns a tk instance for this configuration.

        :param sg_user: Authenticated Shotgun user to associate
                        the tk instance with.
        """
        # set up the environment to pass on to the tk instance
        pipeline_config = {
            "project_id": self._project_id,
            "pipeline_config_id": self._pipeline_config_id,
            "bundle_cache_paths": self._bundle_cache_fallback_paths
        }

        log.debug("Setting External config data: %s" % pipeline_config)
        os.environ[constants.ENV_VAR_EXTERNAL_PIPELINE_CONFIG_DATA] = pickle.dumps(pipeline_config)

        # call base class
        return super(BakedConfiguration, self).get_tk_instance(sg_user)

    @classmethod
    def bake_config_scaffold(cls, path, sg_connection, plugin_id, config_descriptor):
        """
        Helper method that can be used to generate a baked scaffold in a given path.

        :param path: Path to generate scaffold in.
        :param sg_connection: Shotgun API instance
        :param plugin_id: Plugin id string to identify the scope for a particular plugin
                          or integration. For more information,
                          see :meth:`~sgtk.bootstrap.ToolkitManager.plugin_id`. For
                          non-plugin based toolkit projects, this value is None.
        :param config_descriptor: Descriptor object describing the configuration.
        """
        config_writer = ConfigurationWriter(ShotgunPath.from_current_os_path(path), sg_connection)

        config_writer.ensure_project_scaffold()

        config_descriptor.copy(os.path.join(path, "config"))

        config_writer.install_core(config_descriptor, bundle_cache_fallback_paths=[])

        config_writer.write_pipeline_config_file(
            pipeline_config_id=None,
            project_id=None,
            plugin_id=plugin_id,
            bundle_cache_fallback_paths=[],
            source_descriptor=config_descriptor
        )

    @property
    def has_local_bundle_cache(self):
        """
        If True, indicates that pipeline configuration has a local bundle cache. If False, it
        depends on the global bundle cache.
        """
        # Baked configurations always have a local bundle cache.
        return True
