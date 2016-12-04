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
import sys
import re
import logging
import xml.etree.ElementTree as XML_ET

from ..errors import TankError
from ..log import LogManager
from ..util.loader import load_plugin

from . import constants
from . import validation

from .bundle import resolve_setting_value
from .engine import get_env_and_descriptor_for_engine

# std core level logger
core_logger = LogManager.get_logger(__name__)

def create_engine_launcher(tk, context, engine_name):
    """
    Factory method that creates a Toolkit engine specific
    SoftwareLauncher instance.

    :param tk: :class:`~sgtk.Sgtk` Toolkit instance.
    :param context: :class:`~sgtk.Context` Context to launch the DCC in.
    :param engine_name: (str) Name of the Toolkit engine associated with
                        the DCC(s) to launch.
    :returns: :class:`SoftwareLauncher` subclass instance or None.
    """
    # Get the engine environment and descriptor using engine.py code
    (env, engine_descriptor) = get_env_and_descriptor_for_engine(
        engine_name, tk, context
    )

    # Make sure it exists locally
    if not engine_descriptor.exists_local():
        raise TankError(
            "Cannot create %s software launcher! %s does not exist on disk." %
            (engine_name, engine_descriptor)
        )

    # Get path to engine startup code and load it.
    engine_path = engine_descriptor.get_path()
    plugin_file = os.path.join(
        engine_path, constants.ENGINE_SOFTWARE_LAUNCHER_FILE
    )

    # Since we don't know what version of the engine is currently
    # installed, the plugin file may not exist.
    if not os.path.isfile(plugin_file):
        # Nothing to do.
        core_logger.debug(
            "SoftwareLauncher plugin file '%s' does not exist!" % plugin_file
        )
        return None

    core_logger.debug("Loading SoftwareLauncher plugin '%s' ..." % plugin_file)
    class_obj = load_plugin(plugin_file, SoftwareLauncher)
    launcher = class_obj(tk, context, engine_name, env)
    core_logger.debug("Created SoftwareLauncher instance: %s" % launcher)

    # Return the SoftwareLauncher instance
    return launcher


class SoftwareLauncher(object):
    """
    Functionality related to the discovery and launch of a DCC
    """
    def __init__(self, tk, context, engine_name, env):
        """
        Constructor.

        :param tk: :class:`~sgtk.Sgtk` Toolkit instance
        :param context: :class:`~sgtk.Context` A context object to
                        define the context on disk where the engine
                        is operating
        :param engine_name: (str) Name of the Toolkit engine associated
                            with the DCC(s) to launch.
        :param env: An Environment object to associate with this launcher.
        """

        # get the engine settings
        settings = env.get_engine_settings(engine_name)

        # get the descriptor representing the engine
        descriptor = env.get_engine_descriptor(engine_name)

        # check that the context contains all the info that the launcher needs
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

        # Once the engine settings and descriptor have been validated,
        # initialize members of this class
        self.__tk = tk
        self.__context = context
        self.__environment = env
        self.__engine_settings = settings
        self.__engine_descriptor = descriptor
        self.__engine_name = engine_name

    ##########################################################################################
    # properties

    @property
    def context(self):
        """
        The context associated with this launcher.

        :returns: :class:`~sgtk.Context`
        """
        return self.__context

    @property
    def descriptor(self):
        """
        Internal method - not part of Tank's public interface.
        This method may be changed or even removed at some point in the future.
        We leave no guarantees that it will remain unchanged over time, so
        do not use in any app code.
        """
        return self.__engine_descriptor

    @property
    def settings(self):
        """
        Internal method - not part of Tank's public interface.
        This method may be changed or even removed at some point in the future.
        We leave no guarantees that it will remain unchanged over time, so
        do not use in any app code.
        """
        return self.__engine_settings

    @property
    def sgtk(self):
        """
        Returns the Toolkit API instance associated with this item

        :returns: :class:`~sgtk.Sgtk`
        """
        return self.__tk

    @property
    def disk_location(self):
        """
        The folder on disk where this item is located.
        This can be useful if you want to write app code
        to retrieve a local resource::

            app_font = os.path.join(self.disk_location, "resources", "font.fnt")
        """
        path_to_this_file = os.path.abspath(sys.modules[self.__module__].__file__)
        return os.path.dirname(path_to_this_file)

    @property
    def display_name(self):
        """
        The display name for the item. Automatically
        appends 'Startup' to the end of the display
        name if that string is missing from the display
        name (e.g. Maya Engine Startup)

        :returns: display name as string
        """
        disp_name = self.descriptor.display_name
        if not disp_name.lower().endswith("startup"):
            # Append "Startup" to the default descriptor
            # display_name to distinguish it from the
            # engine's display name.
            disp_name = "%s Startup" % disp_name
        return disp_name

    @property
    def engine_name(self):
        """
        The TK engine name this launcher is based on.

        :returns: String TK engine name
        """
        return self.__engine_name

    @property
    def logger(self):
        """
        Standard python logger for this engine, app or framework.
        Use this whenever you want to emit or process log messages.

        :returns: logging.Logger instance
        """
        return LogManager.get_logger("env.%s.%s.startup" %
            (self.__environment.name, self.__engine_name)
        )

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

    def scan_software(self, versions=None, display_name=None, icon=None):
        """
        Performs a scan for software installations.

        :param versions: List of strings representing versions
                         to search for. If set to None, search
                         for all versions. A version string is
                         DCC-specific but could be something
                         like "2017", "6.3v7" or "1.2.3.52"
        :param display_name : (optional) String to use to describe the
                              resulting SoftwareVersion(s) in graphical
                              displays.
        :param icon: (optional) Path to icon to use with the resulting
                     SoftwareVersion(s) in graphical displays.
        :returns: List of :class:`SoftwareVersion` instances
        """
        raise NotImplementedError

    def prepare_launch(self, exec_path, args, options, file_to_open=None):
        """
        Prepares the given software for launch

        :param exec_path: Path to DCC executable to launch
        :param args: Command line arguments as strings
        :param options: DCC specific options to pass
        :param file_to_open: (Optional) Full path name of a file to open on launch
        :returns: LaunchInformation instance
        """
        raise NotImplementedError

    ##########################################################################################
    # public methods

    def get_setting(self, key, default=None):
        """
        Get a value from the item's settings::

            >>> app.get_setting('entity_types')
            ['Sequence', 'Shot', 'Asset', 'Task']

        :param key: config name
        :param default: default value to return
        :returns: Value from the environment configuration
        """
        # An old use case exists whereby the key does not exist in the
        # config schema so we need to account for that.
        schema = self.descriptor.configuration_schema.get(key, None)

        # Use engine.py method to resolve the setting value
        return resolve_setting_value(
            self.sgtk, self.engine_name, schema, self.settings, key, default
        )


class SoftwareVersion(object):
    """
    Container class that stores properties of a DCC that
    are useful for Toolkit Engine Startup functionality.
    """
    def __init__(self, name, version, display_name, path, icon=None):
        """
        Constructor.

        :param name: Internal name for the SoftwareVersion
                     (e.g. Maya)
        :param version: Explicit (string) version of the DCC represented
                        (e.g. 2017)
        :param display_name: Name to use for any graphical displays
        :param path: Full path to the DCC executable.
        :param icon: (Optional) Full path to the icon to use for graphical
                     displays of this SoftwareVersion.
        """
        self._name = name
        self._version = version
        self._display_name = display_name
        self._path = path
        self._icon_path = icon

    @property
    def name(self):
        """
        The internal name for this SoftwareVersion

        :returns: String name
        """
        return self._name

    @property
    def version(self):
        """
        An explicit version of the DCC represented by this SoftwareVersion.

        :returns: String version
        """
        return self._version

    @property
    def display_name(self):
        """
        Name to use for this SoftwareVersion in graphical displays.

        :returns: String display name
        """
        return self._display_name

    @property
    def path(self):
        """
        Specified path to the DCC executable. May be relative.

        :returns: String path
        """
        return self._path

    @property
    def icon(self):
        """
        Path to the icon to use for graphical displays of this
        SoftwareVersion

        :returns: String path
        """
        return self._icon_path


class LaunchInformation(object):
    """
    Stores blueprints for how to launch a specific DCC.
    """
    def __init__(self, path=None, args=None, environ=None):
        """
        Constructor

        :param path: Resolved path to DCC
        :param args: Args to pass on the command line when launching the DCC
        :param environ: Dict of environment variables : value that must be
                        set to successfully launch the DCC.
        """
        # Initialize members
        self._path = path
        self._args = args or ""
        self._environment = environ or {}

    @property
    def path(self):
        """
        The DCC path to launch

        :returns: String path
        """
        return self._path

    @property
    def args(self):
        """
        Arguments to pass to the DCC on launch

        :returns: String args
        """
        return self._args

    @property
    def environment(self):
        """
        Dictionary of environment variables to set before
        launching DCC.

        :returns: Dict {env_var: value}
        """
        return self._environment
