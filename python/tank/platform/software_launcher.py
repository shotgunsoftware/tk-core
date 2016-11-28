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

from .bundle import resolve_default_value
from .engine import get_env_and_descriptor_for_engine

# std core level logger
core_logger = LogManager.get_logger(__name__)


def create_engine_launcher(tk, context, engine_name):
    """
    Factory method that creates a Toolkit engine specific
    SoftwareLauncher instance.

    :param tk: :class:`~sgtk.Sgtk` Toolkit instance.
    :param context: :class:`~sgtk.Context` Context to launch the DCC in.
    :param engine_name: (str) Name of the Toolkit engine associated with the
                        DCC(s) to launch.
    :returns: :class:`SoftwareLauncher` subclass instance.
    """
    try:
        # Get the engine environment and descriptor using Engine.py code
        (env, engine_descriptor) = get_env_and_descriptor_for_engine(engine_name, tk, context)

        # Make sure it exists locally
        if not engine_descriptor.exists_local():
            raise TankError("Cannot create %s software launcher! %s does not exist on disk" %
                (engine_name, engine_descriptor)
            )

        # Get path to engine startup code and load it.
        engine_path = engine_descriptor.get_path()
        plugin_file = os.path.join(engine_path, constants.ENGINE_SOFTWARE_LAUNCHER_FILE)
        class_obj = load_plugin(plugin_file, SoftwareLauncher)
        launcher = class_obj(tk, context, engine_name, env)

    except Exception, e:
        # Trap and log the exception and let it bubble in unchanged form
        core_logger.exception("Exception raised in create_engine_launcher :\n%s" % e)
        raise

    # Return the instantiated SoftwareLauncher
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
        self._synergy_paths = None

        # check general debug log setting and if this flag is turned on,
        # adjust the global setting
        if self.get_setting("debug_logging", False):
            LogManager().global_debug = True
            self.logger.debug(
                "Detected setting 'config/env/%s.yml:%s.debug_logging: true' "
                "in your environment configuration. Turning on debug output." %
                (self.__environment.name, self.__engine_name)
            )


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
        if disp_name and "startup" not in disp_name.lower():
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
        Resolve a SoftwareVersion instance for the input DCC path.

        :param path: Full path to a DCC
        :returns: SoftwareVersion instance
        """
        raise NotImplementedError

    def prepare_launch(self, software_version, args, options, file_to_open=None):
        """
        Prepares the given software for launch

        :param software_version: Software Version to launch
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
        # The post processing code requires the schema to introspect the
        # setting's types, defaults, etc. An old use case exists whereby the key
        # does not exist in the config schema so we need to account for that.
        schema = self.descriptor.configuration_schema.get(key, None)

        # Get the value for the supplied key
        if key in self.settings:
            # Value provided by the settings
            value = self.settings[key]
        elif schema:
            # Resolve a default value from the schema. This checks various
            # legacy default value forms in the schema keys.
            value = resolve_default_value(schema, default, self.__engine_name)
        else:
            # Nothing in the settings, no schema, fallback to the supplied
            # default value
            value = default

        # We have a value of some kind and a schema. Allow the post
        # processing code to further resolve the value.
        if value and schema:
            value = self.__post_process_settings_r(key, value, schema)
        return value

    def synergy_paths(self):
        """
        Scans the local file system using a list of search paths for
        Autodesk Synergy Config files (.syncfg).

        :returns: List of path names to Synergy Config files found
                  in the local environment
        """
        if self._synergy_paths is None:
            # Check for custom paths defined by the SYNHUB_CONFIG_PATH
            # env var.
            env_paths = os.environ.get("SYNHUB_CONFIG_PATH")
            search_paths = []
            if isinstance(env_paths, basestring):
                # This can be a list of directories and/or files.
                search_paths = env_paths.split(os.pathsep)

            # Check the platfom-specific default installation path
            # if no paths were set in the environment
            elif sys.platform == "darwin":
                search_paths = ["/Applications/Autodesk/Synergy/"]
            elif sys.platform == "win32":
                search_paths = ["C:\\ProgramData\\Autodesk\\Synergy\\"]
            elif sys.platform == "linux2":
                search_paths = ["/opt/Autodesk/Synergy/"]
            else:
                self.logger.debug(
                    "Unable to determine Autodesk Synergy paths for platform "%
                    sys.platform
                )

            # Set a default value, so we stop looking for them.
            # @todo: Possibly implement a reset_synergy_paths() method?
            self._synergy_paths = []
            for search_path in search_paths:
                if os.path.isdir(search_path):
                    # Get the list of *.syncfg files in this directory
                    self._synergy_paths.extend([
                        os.path.join(search_path, f) for f in os.listdir(search_path)
                        if f.endswith(".syncfg")
                    ])
                elif os.path.isfile(search_path) and search_path.endswith(".syncfg"):
                    # Add the specified Synergy Config file directly to the list of paths.
                    self._synergy_paths.append(search_path)

            self.logger.info("Autodesk Synergy paths set to : %s" % self._synergy_paths)
        return self._synergy_paths


    ##########################################################################################
    # internal helper methods

    def _synergy_data_from_config(self, cfg_path):
        """
        For Autodesk DCCs, retrieve the Synergy Config data from the specified
        configuation file.

        :param cfg_path: Full path to Synergy Config (.syncfg) XML file
        :returns: Dictionary representation of <Application> data from the
                  input config file. Returned dictionary may also be empty.
        :raises TankError: If there are any XML parsing errors or dict()
                           conversion errors.
        """
        if not os.path.isfile(cfg_path):
            self.logger.info("Synergy config file [%s] does not exist." % cfg_path)
            return {}

        try:
            # Parse the Synergy Config file as XML
            doc = XML_ET.parse(cfg_path)
        except Exception, e:
            raise TankError(
                "Caught exception attempting to parse [%s] as XML.\n%s" %
                (cfg_path, e)
            )

        try:
            # Find the <Application> element that contains the data
            # we want.
            app_elem = doc.getroot().find("Application")
            if app_elem is None:
                self.logger.warning(
                    "No <Application> found in Synergy config file '%s'." %
                    (cfg_path)
                )
                return {}

            # Convert the element's attribute/value pairs to a dictionary
            synergy_data = dict(app_elem.items())
        except Exception, e:
            raise TankError(
                "Caught unknown exception retrieving <Application> data from %s:\n%s" %
                (cfg_path, e)
            )

        return synergy_data

    def _software_version_from_synergy(self, cfg_path=None, syn_data=None):
        """
        Creates a SoftwareVersion instance based on the Synergy configuration
        data from either the input Synergy Config (.syncfg) file or the data
        dictionary already parsed from a Synergy Config file.

        Must specify cfg_path or syn_data. If both are specified, cfg_path
        is ignored.

        :param cfg_path: Full path to a Synergy Config (.syncfg) XML file
        :param syn_data: Synergy data parsed from a Synergy Config file
        :returns: :class:`SoftwareVersion` SoftwareVersion instance or None.
        """
        if syn_data is None:
            # Assume a configuation file has been specified to parse
            syn_data = self._synergy_data_from_config(cfg_path)
        if not syn_data:
            # Config path not specified or couldn't be parsed.
            self.logger.debug("Could not parse synergy data from input config '%s'." % cfg_path)
            self.logger.debug("   or input synergy data : %s" % syn_data)
            return None

        # Return SoftwareVersion instance built from Synergy data
        return SoftwareVersion(
                    syn_data["Name"], syn_data["NumericVersion"],
                    syn_data["StringVersion"], syn_data["ExecutablePath"],
               )

    def _synergy_data_from_executable(self, exec_path):
        """
        Finds the Synergy Config data relevant to the input DCC path.

        :param exec_path: Full path to DCC.
        :returns: Dictionary populated with Synergy Config data or empty.
        """
        found_data = None
        path_matches = []
        for cfg_path in self.synergy_paths():
            syn_data = self._synergy_data_from_config(cfg_path)
            # Get the ExecutablePath from the Synergy Config file
            # and compare it to the input exec_path.
            data_exec = syn_data.get("ExecutablePath")
            if data_exec == exec_path:
                # Exact match, got the data we need, so break.
                found_data = syn_data
                break
            elif str(data_exec).startswith(exec_path):
                # Keep track of things that might be close.
                path_matches.append(syn_data)

        if found_data:
            # Exact match to what was requested.
            return found_data

        if len(path_matches) == 1:
            # Only one close match was found.
            return path_matches[0]

        # Couldn't be determined.
        return {}


    def __post_process_settings_r(self, key, value, schema):
        """
        Recursive post-processing of settings values

        :param key: Key to find value for from schema or default
        :param value: Default value to return if no default value
                      is found in the schema.
        :param schema: Settings schema containing key
        :returns: Value for key
        """
        settings_type = schema.get("type")

        if settings_type == "list":
            processed_val = []
            value_schema = schema["values"]
            for x in value:
                processed_val.append(self.__post_process_settings_r(key, x, value_schema))

        elif settings_type == "dict":
            items = schema.get("items", {})
            processed_val = value
            for (key, value_schema) in items.items():
                processed_val[key] = self.__post_process_settings_r(
                    key, value[key], value_schema
                )

        elif settings_type == "config_path":
            # this is a config path. Stored on the form
            # foo/bar/baz.png, we should translate that into
            # PROJECT_PATH/tank/config/foo/bar/baz.png
            config_folder = self.__tk.pipeline_configuration.get_config_location()
            adjusted_value = value.replace("/", os.path.sep)
            processed_val = os.path.join(config_folder, adjusted_value)

        elif type(value) == str and value.startswith("hook:"):
            # handle the special form where the value is computed in a hook.
            #
            # if the template parameter is on the form
            # a) hook:foo_bar
            # b) hook:foo_bar:testing:testing
            #
            # The following hook will be called
            # a) foo_bar with parameters []
            # b) foo_bar with parameters [testing, testing]
            #
            chunks = value.split(":")
            hook_name = chunks[1]
            params = chunks[2:]
            processed_val = self.__tk.execute_core_hook(
                hook_name, setting=key, bundle_obj=self, extra_params=params
            )
        else:
            # pass-through
            processed_val = value

        return processed_val


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
        :param path: Full path to the DCC executable. This path may contain
                     {version} and/or {v1}..{vN} patterns or ENV variables.
        :param icon: (Optional) Full path to the icon to use for graphical
                     displays of this SoftwareVersion. This path may contain
                     {version} and/or {v1}..{vN} patterns or ENV variables.
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
        Replaces any {version} and/or {v1}...{vN} patterns in the
        display_name string originally specified.

        :returns: String display name
        """
        return _apply_version_to_setting(self._display_name, self._version)

    @display_name.setter
    def display_name(self, new_value):
        """
        Set the display name to the new input value.

        :param new_value: Display name to use as a string.
        """
        self._display_name = new_value

    @property
    def raw_path(self):
        """
        Input DCC path that may contain {version} and/or {v1}...{vN} patterns
        or environment variables.

        :returns: String path
        """
        return self._path

    @property
    def path(self):
        """
        DCC path with any {version} and/or {v1}...{vN} patterns and/or
        environment variables subtituted appropriately.

        :returns: String path
        """
        ver_path = _apply_version_to_setting(self._path, self._version)
        return os.path.expandvars(ver_path)

    @path.setter
    def path(self, new_value):
        """
        Allow the DCC path to be set post-construction.

        :param new_value: New path to DCC, as a string
        """
        self._path = new_value

    @property
    def raw_icon(self):
        """
        Input path to icon that may contain {version} and/or {v1}...{vN} patterns
        or environment variables.

        :returns: String path
        """
        return self._icon_path

    @property
    def icon(self):
        """
        Icon path with any {version} and/or {v1}...{vN} patterns and/or
        environment variables substituted appropriately.

        :returns: String path
        """
        ver_icon = _apply_version_to_setting(self._icon_path, self._version)
        if ver_icon:
            ver_icon = os.path.expandvars(ver_icon)
        return ver_icon

    @icon.setter
    def icon(self, new_path):
        """
        Allow the icon path to be set post-construction.

        :param new_path: New path to icon
        """
        self._icon_path = new_path


def _apply_version_to_setting(raw_string, version=None):
    """
    Replace any version tokens contained in the raw_string
    with the appropriate version value from the app settings.
    Replaces {version} and {v0}, {v1}, etc. tokens in raw_string
    with their values. The {v} tokens are created by using groups
    defined by () within the version string. For example, if the
    version setting is "(9.0)v4(beta1)"
        {version} = "9.0v4"
        {v0} = "9.0"
        {v1} = "beta1"

    If version is None, we return the raw_string since there's
    no replacement to do.

    :param raw_string: the raw string potentially containing the
                       version tokens (eg. {version}, {v0}, ...)
                       we will be replacing. This string could
                       represent a number of things including a
                       path, an args string, etc.
    :param version: version string to use for the token replacement.

    :returns: string with version tokens replaced with their
              appropriate values
    """
    # Verify there's something to replace.
    if not raw_string or not version:
        return raw_string

    # split version string into tokens defined by ()s
    version_tokens = re.findall(r"\(([^\)]+)\)", version)

    # ensure we have a clean complete version string without ()s
    clean_version = re.sub("[()]", "", version)

    # do the substitution
    ver_string = raw_string.replace("{version}", clean_version)
    for i, token in enumerate(version_tokens):
        ver_string = ver_string.replace("{v%d}" % i, token)
    return ver_string


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
