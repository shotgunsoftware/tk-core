# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from .configuration import Configuration

from .. import LogManager

log = LogManager.get_logger(__name__)


class InstalledConfiguration(Configuration):
    """
    Represents a Toolkit pipeline configuration that is installed at a specific location via the
    ``mac_path``, ``linux_path`` and ``windows_path`` fields that has been setup with the setup project
    command of the pre-zero config project creation wizard in Shotgun Desktop.
    """

    def __init__(self, path, descriptor):
        """
        :param str path: ShotgunPath object describing the path to this configuration
        :param descriptor: ConfigDescriptor for the associated config
        """
        super(InstalledConfiguration, self).__init__(path, descriptor)

    def __str__(self):
        """
        User friendly representation of the configuration.
        """
        return "Installed Configuration at %s" % (self._path.current_os,)

    def __repr__(self):
        """
        Low level representation of the configuration.
        """
        return "<%s>" % str(self)

    def status(self):
        """
        Installed configurations are always up-to-date.

        :returns: LOCAL_CFG_UP_TO_DATE
        """
        log.debug("%s is always up to date:" % self)

        return self.LOCAL_CFG_UP_TO_DATE

    def update_configuration(self):
        """
        No need to update anything, as this configuration type is always up-to-date.
        """
        pass

    @property
    def has_local_bundle_cache(self):
        """
        If True, indicates that pipeline configuration has a local bundle cache. If False, it
        depends on the global bundle cache.
        """
        return True
