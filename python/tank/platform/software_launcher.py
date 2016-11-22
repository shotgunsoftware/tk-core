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
import xml.etree.ElementTree as XML_ET

from ..errors import TankError
from ..log import LogManager
from ..util.loader import load_plugin

from . import constants
from . import validation

from .bundle import resolve_default_value
from .engine import get_env_and_descriptor_for_engine


def create_engine_launcher(tk, context, engine_name):
    """
    Factory method that creates an engine specific 
    SoftwareLauncher instance.

    :param tk: :class:`~sgtk.Sgtk` Toolkit instance.
    :param context: :class:`~sgtk.Context` Context to launch the DCC in.
    :param engine_name: (str) Name of the Toolkit engine associated with the
                        DCC(s) to launch.
    :returns: :class:`SoftwareLauncher` instance.
    """
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

    # Instantiate the SoftwareLauncher
    engine_launcher = class_obj(tk, context, engine_name, env)

    return engine_launcher


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

        # Once the engine settings and descriptor have been validated,
        # initialize members of this class
        self.__tk = tk
        self.__context = context
        self.__environment = env
        self.__engine_settings = settings
        self.__engine_descriptor = descriptor
        self.__engine_name = engine_name
        self.__synergy_paths = None

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
        return self.__context

    @property
    def descriptor(self):
        return self.__engine_descriptor

    @property
    def settings(self):
        return self.__engine_settings

    @property
    def sgtk(self):
        return self.__tk
    tank = sgtk

    @property
    def disk_location(self):
        path_to_this_file = os.path.abspath(sys.modules[self.__module__].__file__)
        return os.path.dirname(path_to_this_file)

    @property
    def display_name(self):
        disp_name = self.descriptor.display_name
        if disp_name:
            disp_name = "%s Startup" % disp_name
        return disp_name

    @property
    def logger(self):
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

    @property
    def synergy_paths(self):
        if self.__synergy_paths is None:
            env_paths = os.environ.get("SYNHUB_CONFIG_PATH")
            if isinstance(env_paths, basestring):
                search_paths = env_paths.split(os.pathsep)
            elif sys.platform == "darwin":
                search_paths = ["/Applications/Autodesk/Synergy/"]
            elif sys.platform == "win32":
                search_paths = ["C:\\ProgramData\\Autodesk\\Synergy\\"]
            elif sys.platform == "linux2":
                search_paths = ["/opt/Autodesk/Synergy/"]
            else
                self.logger.debug(
                    "Unable to determine Autodesk Synergy paths for platform "%
                    sys.platform
                )
                search_paths = []

            self.__synergy_paths = []
            for search_path in search_paths:
                if os.path.isdir(search_path):
                    self.__synergy_paths.extend([
                        "%s/%s" % (search_path, f) for f in os.listdir(search_path)
                        if f.endswith(".syncfg")
                    ])
                elif os.path.isfile(search_path) and search_path.endswith(".syncfg"):
                    self.__synergy_paths.append(search_path)

            self.logger.info("Autodesk Synergy paths set to : %s" % self.__synergy_paths)
        return self.__synergy_paths


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
    # public methods
    def get_setting(self, key, default=None):
        schema = self.descriptor.configuration_schema.get(key, None)
        if key in self.settings:
            value = self.settings[key]
        elif schema:
            value = resolve_default_value(schema, default, self.__engine_name)
        else:
            value = default

        if value and schema:
            value = self.__post_process_settings_r(key, value, schema)
        return value

    def get_template(self, key):
        return self.get_template_by_name(self.get_setting(key))

    def get_template_by_name(self, template_name):
        return self.sgtk.templates.get(template_name)


    ##########################################################################################
    # internal helper methods

    def _synergy_data_from_config(self, cfg_path):
        if not os.path.isfile(cfg_path):
            self.logger.info("Synergy config file [%s] does not exist." % cfg_path)
            return {}

        try:
            doc = XML_ET.parse(cfg_path)
        except Exception, e:
            raise TankError(
                "Caught exception attempting to parse [%s] as XML.\n%s" %
                (cfg_path, e)
            )

        try:
            app_elem = doc.getroot().find("Application")
            if app_elem is None:
                self.logger.warning(
                    "No <Application> found in Synergy config file '%s'." % 
                    (cfg_path)
                )
                return {}
            synergy_data = dict(app_elem.items())
        except Exception, e:
            raise TankError(
                "Caught unknown exception retrieving <Application> data from %s:\n%s" %
                (cfg_path, e)
            )

        return synergy_data

    def _software_version_from_synergy(self, cfg_path=None, syn_data=None):
        if syn_data is None:
            syn_data = self._synergy_data_from_config(cfg_path)
        if not syn_data:
            self.logger.debug("Could not parse synergy data from input config '%s'." % cfg_path)
            self.logger.debug("   or input synergy data : %s" % syn_data)
            return None

        sv = SoftwareVersion(
                syn_data["Name"],
                syn_data["NumericVersion"],
                syn_data["StringVersion"],
                syn_data["ExecutablePath"],
        )
        return sv

    def _synergy_data_from_executable(self, exec_path):
        found_data = None
        path_matches = []
        for cfg_path in self.synergy_paths:
            syn_data = self._synergy_data_from_config(cfg_path)
            data_exec = syn_data.get("ExecutablePath")
            if data_exec == exec_path:
                found_data = syn_data
                break
            elif str(data_exec).startswith(exec_path):
                path_matches.append(syn_data)

        if found_data:
            return found_data

        if len(path_matches) == 1:
            return path_matches[0]

        return {}


    def __post_process_settings_r(self, key, value, schema):
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
            config_folder = self.__tk.pipeline_configuration.get_config_location()
            adjusted_value = value.replace("/", os.path.sep)
            processed_val = os.path.join(config_folder, adjusted_value)

        elif type(value) == str and value.startswith("hook:"):
            chunks = value.split(":")
            hook_name = chunks[1]
            params = chunks[2:]
            processed_val = self.__tk.execute_core_hook(
                hook_name, setting=key, bundle_obj=self, extra_params=params
            )
        else:
            processed_val = value

        return processed_val


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
        return _apply_version_to_setting(self._display_name, self._version)

    @property
    def raw_path(self):
        return self._path

    @property
    def path(self):
        ver_path = _apply_version_to_setting(self._path, self._version)
        return os.path.expandvars(ver_path)

    @property
    def raw_icon(self):
        return self._icon_path
        
    @property
    def icon(self):
        ver_icon = _apply_version_to_setting(self._icon_path, self._version)
        return os.path.expandvars(ver_icon)

    @icon.setter
    def icon(self, new_path):
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

