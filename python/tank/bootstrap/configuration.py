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
import inspect

from .import_handler import CoreImportHandler

from .. import LogManager

log = LogManager.get_logger(__name__)


class Configuration(object):
    """
    An abstraction around a toolkit configuration.

    The configuration is identified by a ConfigurationDescriptor
    object and may or may not exist on disk.
    """

    (LOCAL_CFG_UP_TO_DATE, LOCAL_CFG_MISSING, LOCAL_CFG_DIFFERENT, LOCAL_CFG_INVALID) = range(4)

    def __init__(self, path):
        """
        Constructor.

        :param path: ShotgunPath object describing the path to this configuration
        """
        self._path = path

    def status(self):
        """
        Compares the actual configuration installed on disk against the
        associated configuration described by the descriptor passed in via
        the class constructor.

        :returns: LOCAL_CFG_UP_TO_DATE, LOCAL_CFG_MISSING,
                  LOCAL_CFG_DIFFERENT, or LOCAL_CFG_INVALID
        """
        raise NotImplementedError

    def update_configuration(self):
        """
        Ensure that the configuration is up to date with the one
        given by the associated descriptor.

        This method fails gracefully and attempts to roll back to a
        stable state on failure.
        """
        raise NotImplementedError

    def get_tk_instance(self, sg_user):
        """
        Returns a tk instance for this configuration.

        :param sg_user: Authenticated Shotgun user to associate
                        the tk instance with.
        """
        path = self._path.current_os
        core_path = os.path.join(path, "install", "core", "python")

        # swap the core out
        CoreImportHandler.swap_core(core_path)

        # perform a local import here to make sure we are getting
        # the newly swapped in core code
        from .. import api
        api.set_authenticated_user(sg_user)
        tk = api.tank_from_path(path)

        log.debug("Bootstrapped into tk instance %r" % tk)
        log.debug("Core API code located here: %s" % inspect.getfile(tk.__class__))

        return tk




