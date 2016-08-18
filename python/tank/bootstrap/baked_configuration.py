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

log = LogManager.get_logger(__name__)

class BakedConfiguration(Configuration):
    """
    An abstraction around a toolkit configuration.

    The configuration is identified by a ConfigurationDescriptor
    object and may or may not exist on disk.
    """

    def __init__(
            self,
            path,
            sg,
            project_id,
            entry_point,
            pipeline_config_id,
            bundle_cache_fallback_paths
    ):
        """
        Constructor.

        :param path: ShotgunPath object describing the path to this configuration
        :param sg: Shotgun API instance
        :param project_id: Project id for the shotgun project associated with the
                           configuration. For a site-level configuration, this
                           can be set to None.
        :param entry_point: Entry point string to identify the scope for a particular plugin
                            or integration. For more information,
                            see :meth:`~sgtk.bootstrap.ToolkitManager.entry_point`. For
                            non-plugin based toolkit projects, this value is None.
        :param pipeline_config_id: Pipeline Configuration id for the shotgun
                                   pipeline config id associated. If a config does
                                   not have an associated entity in Shotgun, this
                                   should be set to None.
        :param bundle_cache_fallback_paths: List of additional paths where apps are cached.
        """
        super(BakedConfiguration, self).__init__(path)
        self._path = path
        self._sg_connection = sg
        self._project_id = project_id
        self._entry_point = entry_point
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

        This method fails gracefully and attempts to roll back to a
        stable state on failure.
        """
        # the baked configuration gets updated at build time

    @classmethod
    def bake_config_scaffold(cls, path, sg_connection, entry_point, config_descriptor):
        """
        Generate config

        :param path:
        :return:
        """
        config_writer = ConfigurationWriter(path, sg_connection)
        config_writer.ensure_project_scaffold()
        config_writer.install_core(config_descriptor, bundle_cache_fallback_paths=[])
        config_writer.write_bare_pipeline_config_file(entry_point)

    def get_tk_instance(self, sg_user):
        """
        Returns a tk instance for this configuration.

        :param sg_user: Authenticated Shotgun user to associate
                        the tk instance with.
        """
        # set up the environment
        os.environ["SGTK_PROJECT_ID"] = self._project_id
        os.environ["SGTK_PIPELINE_CONFIGURATION_ID"] = self._pipeline_config_id
        os.environ["SGTK_BUNDLE_CACHE_FALLBACK_PATHS"] = self._bundle_cache_fallback_paths

        # call base class
        return super(BakedConfiguration, self).get_tk_instance(sg_user)
