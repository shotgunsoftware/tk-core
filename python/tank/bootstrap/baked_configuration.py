# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

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

    def __init__(self, path):
        """
        Constructor.

        :param path: ShotgunPath object describing the path to this configuration
        """
        super(BakedConfiguration, self).__init__(path)
        self._path = path

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


