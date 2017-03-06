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
Defines the base class for DCC application launchers all Toolkit engines
should implement.
"""

import os
import sys
import pprint

from ..errors import TankError
from ..log import LogManager
from ..util.loader import load_plugin
from ..util.version import is_version_older

from . import constants
from . import validation

from .bundle import resolve_setting_value
from .engine import get_env_and_descriptor_for_engine

# std core level logger
core_logger = LogManager.get_logger(__name__)


def create_engine_launcher(tk, context, engine_name):
    """
    Factory method that creates a :class:`SoftwareLauncher` subclass 
    instance implemented by a toolkit engine in the environment config
    that can be used by a custom script or toolkit app. The engine 
    subclass manages the business logic for DCC executable path 
    discovery and the environmental requirements for launching the DCC.
    Toolkit is automatically started up during the DCC's launch phase.
    A very simple example of how this works is demonstrated here::

        >>> import subprocess
        >>> import sgtk
        >>> tk = sgtk.sgtk_from_path("/studio/project_root")
        >>> context = tk.context_from_path("/studio/project_root/sequences/AAA/ABC/Light/work")
        >>> launcher = sgtk.platform.create_engine_launcher(tk, context, "tk-maya")
        >>> software_versions = launcher.scan_software()
        >>> launch_info = launcher.prepare_launch(software_versions[0].path, args, "/studio/project_root/sequences/AAA/ABC/Light/work/scene.ma")
        >>> subprocess.Popen([launch_info.path + " " + launch_info.args], env=launch_info.environment)

    where ``software_versions`` is a list of :class:`SoftwareVersion`
    instances and ``launch_info`` is a :class:`LaunchInformation`
    instance. This example will launch the first version of Maya
    found installed on the local filesystem, automatically start
    the tk-maya engine for that Maya session, and open
    /studio/project_root/sequences/AAA/ABC/Light/work/scene.ma.

    :param tk: :class:`~sgtk.Sgtk` Toolkit instance.
    :param context: :class:`~sgtk.Context` Context to launch the DCC in.
    :param str engine_name: Name of the Toolkit engine associated with
                            the DCC(s) to launch.

    :rtype: :class:`SoftwareLauncher` instance or ``None`` if the 
            engine can be found on disk, but no ``startup.py`` file exists.
    :raises: :class:`TankError` if the specified engine cannot be found
             on disk.
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
    Functionality related to the discovery and launch of a DCC. This class
    should only be constructed through the :meth:`create_engine_launcher()`
    factory method.
    """
    def __init__(self, tk, context, engine_name, env):
        """
        :param tk: :class:`~sgtk.Sgtk` Toolkit instance
        :param context: :class:`~sgtk.Context` A context object to
                        define the context on disk where the engine
                        is operating
        :param str engine_name: Name of the Toolkit engine associated
                                with the DCC(s) to launch.
        :param env: An :class:`~sgtk.platform.environment.Environment` object to
                    associate with this launcher.
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
        # initialize members of this class. Since this code only runs
        # during the pre-launch phase of an engine, there are no
        # opportunities to change the Context or environment. Safe
        # to cache these values.
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
        The toolkit engine name this launcher is based on.

        :returns: String engine name
        """
        return self.__engine_name

    @property
    def logger(self):
        """
        Standard python logger for this engine, app or framework.
        Use this whenever you want to emit or process log messages.

        :returns: :class:`logging.Logger` instance
        """
        return LogManager.get_logger("sgtk.env.%s.%s.startup" %
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
    def minimum_supported_version(self):
        """
        The minimum software version that is supported by the launcher.
        Returned as a string, for example "2015" or "2015.3.sp3".
        Returns ``None`` if no constraint has been set.
        Also see related method :meth:`~is_version_supported`.
        """
        # returns none by default, subclassed by implementing classes
        return None

    ##########################################################################################
    # abstract methods

    def scan_software(self, versions=None):
        """
        Performs a scan for software installations.

        :param list versions: List of strings representing versions
                              to search for. If set to None or [], search
                              for all versions. A version string is
                              DCC-specific but could be something
                              like "2017", "6.3v7" or "1.2.3.52"
        :returns: List of :class:`SoftwareVersion` instances
        """
        raise NotImplementedError

    def prepare_launch(self, exec_path, args, file_to_open=None):
        """
        This is an abstract method that must be implemented by a subclass. The
        engine implementation should prepare an environment to launch the specified
        executable path in.

        .. note:: By returning an executable path and args string, we allow for
                  a workflow where the engine launcher can rewrite the launch
                  sequence in arbitrary ways. For example, if a DCC has a
                  pre-check phase that requires input from a human, a different
                  executable path that launches a standalone UI which in turn
                  launches the specified path can be returned with the appropriate
                  args.

        :param str exec_path: Path to DCC executable to launch
        :param str args: Command line arguments as strings
        :param str file_to_open: (optional) Full path name of a file to open on launch
        :returns: :class:`LaunchInformation` instance
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

    def get_standard_plugin_environment(self):
        """
        Create a standard plugin environment, suitable for
        plugins to utilize. This will compute the following
        environment variables:

        - ``SHOTGUN_SITE``: The current shotgun site url
        - ``SHOTGUN_ENTITY_TYPE``: The current context
        - ``SHOTGUN_ENTITY_ID``: The current context
        - ``SHOTGUN_PIPELINE_CONFIGURATION_ID``: The current pipeline config id

        :returns: dictionary of environment variables
        """
        self.logger.debug("Computing standard plugin environment variables...")
        env = {}

        # site
        env["SHOTGUN_SITE"] = self.sgtk.shotgun_url

        # pipeline config id
        # note: get_shotgun_id() returns None for unmanaged configs.
        pipeline_config_id = self.sgtk.pipeline_configuration.get_shotgun_id()
        if pipeline_config_id:
            env["SHOTGUN_PIPELINE_CONFIGURATION_ID"] = str(pipeline_config_id)
        else:
            self.logger.debug("Unmanaged config. Not setting SHOTGUN_PIPELINE_CONFIGURATION_ID.")

        # get the most accurate entity, first see if there is a task, then entity then project
        entity_dict = self.context.task or self.context.entity or self.context.project

        if entity_dict:
            env["SHOTGUN_ENTITY_TYPE"] = entity_dict["type"]
            env["SHOTGUN_ENTITY_ID"] = str(entity_dict["id"])
        else:
            self.logger.debug(
                "No context found. Not setting SHOTGUN_ENTITY_TYPE and SHOTGUN_ENTITY_ID."
            )

        self.logger.debug("Returning Plugin Environment: \n%s" % pprint.pformat(env))

        return env

    def is_version_supported(self, version):
        """
        Compares the given version string with the :meth:`~minimum_supported_version`
        and returns a boolean to indicate whether it is supported by the launcher
        or not.

        :param str version: Version string to test, e.g. "2015" or "2017.3.sp4"
        :returns: True if supported, False otherwise.
        """
        if self.minimum_supported_version is None:
            return True

        if is_version_older(version, self.minimum_supported_version):
            return False
        else:
            return True



class SoftwareVersion(object):
    """
    Container class that stores properties of a DCC that
    are useful for Toolkit Engine Startup functionality.
    """
    def __init__(self, version, display_name, path, icon=None):
        """
        :param str version: Explicit version of the DCC represented
                            (e.g. 2017)
        :param str display_name: Name to use for any graphical displays
        :param str path: Full path to the DCC executable.
        :param str icon: (optional) Full path to a 256x256 (or smaller)
                         png file to use for graphical displays of
                         this SoftwareVersion.
        """
        self._version = version
        self._display_name = display_name
        self._path = path
        self._icon_path = icon

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
        SoftwareVersion. Expected to be a 256x256 (or smaller)
        png file.

        :returns: String path
        """
        return self._icon_path


class LaunchInformation(object):
    """
    Stores blueprints for how to launch a specific DCC which includes
    required environment variables, the executable path, and command
    line arguments to pass when launching the DCC. For example, given
    a LaunchInformation instance ``launch_info``, open a DCC using 
    ``subprocess``::

        >>> launch_cmd = "%s %s" % (launch_info.path, launch_info.args)
        >>> subprocess.Popen([launch_cmd], env=launch_info.environment)

    A LaunchInformation instance is generally obtained from an engine's
    subclass implementation of :meth:`SoftwareLauncher.prepare_launch``
    """
    def __init__(self, path=None, args=None, environ=None):
        """
        :param str path: Resolved path to DCC
        :param str args: Args to pass on the command line
                         when launching the DCC
        :param dict environ: Environment variables that
                             must be set to successfully
                             launch the DCC.
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
