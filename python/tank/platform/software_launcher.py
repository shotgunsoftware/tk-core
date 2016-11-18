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
Defines the base class for DCC application launchers all Tank engines 
should implement.
"""

import os
import logging

from ..errors import TankError
from ..log import LogManager
from ..util.loader import load_plugin

from . import constants
from . import validation

from .bundle_base import TankBundleBase
from .engine import get_env_and_descriptor_for_engine
from .engine_logging import ToolkitEngineHandler


def create_engine_launcher(tk, context, engine_name):

    if LogManager().base_file_handler is None:
        LogManager().initialize_base_file_handler(engine_name)

    (env, engine_descriptor) = get_env_and_descriptor_for_engine(engine_name, tk, context)

    if not engine_descriptor.exists_local():
        raise TankError("Cannot create %s software launcher! %s does not exist on disk" %
            (engine_name, engine_descriptor)
        )

    engine_path = engine_descriptor.get_path()
    plugin_file = os.path.join(engine_path, constants.ENGINE_SOFTWARE_LAUNCHER_FILE)
    class_obj = load_plugin(plugin_file, SoftwareLauncher)
    engine_launcher = class_obj(tk, context, engine_name, env)

    return engine_launcher


class SoftwareLauncher(TankBundleBase):
    """
    Functionality related to the discovery and launch of a DCC
    """
    def __init__(self, tk, context, engine_name, env):
        """
        Constructor.

        :param engine_name:
        :param tk: :class:`~sgtk.Sgtk` instance
        :param context: A context object to define the context on disk where the engine is operating
        :type context: :class:`~sgtk.Context`
        :param env: An Environment object to associate with this bundle.
        """

        # get the engine settings
        settings = env.get_engine_settings(engine_name)

        # get the descriptor representing the engine        
        descriptor = env.get_engine_descriptor(engine_name)

        # check that the context contains all the info that the app needs
        validation.validate_context(descriptor, context)
        
        # make sure the current operating system platform is supported
        validation.validate_platform(descriptor)

        # Get the settings for the engine and then validate them
        engine_schema = descriptor.configuration_schema
        validation.validate_settings(
            engine_name,
            tk,
            context,
            engine_schema,
            settings
        )
        
        # create logger for this engine.
        # log will be parented in a sgtk.env.environment_name.engine_instance_name hierarchy
        logger = LogManager.get_logger("env.%s.%s" % (env.name, engine_name))

        TankBundleBase.__init__(self, tk, context, settings, descriptor, env, logger)
        self.__engine_name = engine_name

        logger.addHandler(self.__initialize_logging())

        # check general debug log setting and if this flag is turned on,
        # adjust the global setting
        if self.get_setting("debug_logging", False):
            LogManager().global_debug = True
            self.logger.debug(
                "Detected setting 'config/env/%s.yml:%s.debug_logging: true' "
                "in your environment configuration. Turning on debug output." % (env.name, engine_name)
            )


    ##########################################################################################
    # properties

    @property
    def shotgun(self):
        """
        Returns a Shotgun API handle associated with the currently running
        environment. This method is a convenience method that calls out
        to :meth:`~sgtk.Tank.shotgun`.

        :returns: Shotgun API handle
        """
        return self.sgtk.shotgun
    

    ##########################################################################################
    # abstract methods

    def scan_software(self, versions=None):
        """
        Performs a scan for software installations.

        :param versions: List of strings representing versions
                         to search for. If set to None, search
                         for all versions. A version string is 
                         DCC-specific but could be something 
                         like "2017", "6.3v7" or "1.2.3.52"
        :returns: List of :class:`SoftwareVersion` instances
        """
        raise NotImplementedError

    def resolve_software(self, path):
        """
        Resolve a software instance for given a path

        :param path: 
        :returns: SoftwareVersion instance
        """
        raise NotImplementedError

    def prepare_launch(self, software_version, args, options):
        """
        Prepares the given software for launch

        :param software_version: Software Version to launch
        :param args: Command line arguments as strings
        :param options: DCC specific options to pass
        :returns: LaunchInformation instance
        """
        raise NotImplementedError


    ##########################################################################################
    # internal helper methods

    def __initialize_logging(self):
        """
        Creates a std python logging LogHandler
        that dispatches all log messages to the
        :meth:`Engine._emit_log_message()` method
        in a thread safe manner.

        For engines that do not yet implement :meth:`_emit_log_message`,
        a legacy log handler is used that dispatches messages
        to the legacy output methods log_xxx.

        :return: :class:`python.logging.LogHandler`
        """
        handler = LogManager().initialize_custom_handler(
            ToolkitEngineHandler(self)
        )
        # make it easy for engines to implement a consistent log format
        # by equipping the handler with a standard formatter:
        # [DEBUG tk-maya] message message
        #
        # engines subclassing log output can call
        # handler.format to access this formatter for
        # a consistent output implementation
        # (see _emit_log_message for details)
        #
        formatter = logging.Formatter(
            "[%(levelname)s %(basename)s] %(message)s"
        )
        handler.setFormatter(formatter)

        return handler
    
    def _get_engine_name(self):
        return self.__engine_name


class SoftwareVersion(object):
    def __init__(self, name, version, display_name, path, icon):
        self._name = name
        self._version = version
        self._display_name = display_name
        self._path = path
        self._icon_path = icon

    @property
    def name(self):
        return self._name

    @property
    def version(self):
        return self._version

    @property
    def display_name(self):
        return self._display_name

    @property
    def path(self):
        return self._path

    @property
    def icon_path(self):
        return self._icon_path


class LaunchInformation(object):
    def __init__(self, path=None, args=None, environ=None):
        self._path = path
        self._args = args
        self._environment = environ or {}

    @property
    def path(self):
        """
        The path to launch
        """
        return self._path


    @property
    def args(self):
        """
        List of arguments to pass
        """
        return self._args


    @property
    def environment(self):
        """
        Dictionary of environment variables to set
        """
        return self._environment
