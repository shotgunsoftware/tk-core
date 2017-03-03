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


def create_engine_launcher(tk, context, engine_name, versions=None, products=None):
    """
    Factory method that creates a Toolkit engine specific
    SoftwareLauncher instance.

    :param tk: :class:`~sgtk.Sgtk` Toolkit instance.
    :param context: :class:`~sgtk.Context` Context to launch the DCC in.
    :param str engine_name: Name of the Toolkit engine associated with the
        DCC(s) to launch.
    :param list versions: A list of version strings for filtering software
        versions. See the :class:`SoftwareLauncher` for more info.
    :param list products: A list of product strings for filtering software
        versions. See the :class:`SoftwareLauncher` for more info.
    :rtype: :class:`SoftwareLauncher` instance or None.
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
    launcher = class_obj(tk, context, engine_name, env, versions, products)
    core_logger.debug("Created SoftwareLauncher instance: %s" % launcher)

    # Return the SoftwareLauncher instance
    return launcher


class SoftwareLauncher(object):
    """
    Functionality related to the discovery and launch of a DCC. This class
    should only be constructed through the :meth:`create_engine_launcher()`
    factory method.
    """
    def __init__(self, tk, context, engine_name, env, versions=None, products=None):
        """
        :param tk: :class:`~sgtk.Sgtk` Toolkit instance

        :param context: :class:`~sgtk.Context` A context object to define the
            context on disk where the engine is operating

        :param str engine_name: Name of the Toolkit engine associated
            with the DCC(s) to launch.

        :param env: An :class:`~sgtk.platform.environment.Environment` object to
            associate with this launcher.

        :param list versions: List of strings representing versions to search
            for. If set to None or [], search for all versions. A version string
            is DCC-specific but could be something like "2017", "6.3v7" or
            "1.2.3.52"

        :param list products: List of strings representing product names to
            search for. If set to None or [], search for all products. A product
            string is DCC-specific but could be something like "Houdini FX",
            "Houdini Core" or "Houdini"
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

        # product and version string lists to limit the scope of sw discovery
        self._products = products or []
        self._versions = versions or []

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

        :returns: :class:`logging.Logger` instance
        """
        return LogManager.get_logger(
            "env.%s.%s.startup" %
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
        """
        # returns none by default, subclassed by implementing classes
        return None

    @property
    def products(self):
        """
        A list of product names limiting executable discovery.

        Example::

            ["Houdini", "Houdini Core", "Houdini FX"]
        """
        return self._products

    @property
    def versions(self):
        """
        A list of versions limiting executable discovery.

        Example::

            ["15.5.324", "16.0.1.322"]
        """
        return self._versions


    ##########################################################################################
    # abstract methods

    def prepare_launch(self, exec_path, args, file_to_open=None):
        """
        Prepares the given software for launch

        :param str exec_path: Path to DCC executable to launch
        :param str args: Command line arguments as strings
        :param str file_to_open: (optional) Full path name of a file to open on
            launch
        :returns: :class:`LaunchInformation` instance
        """
        raise NotImplementedError

    def _scan_software(self):
        """
        Abstract method that must be implemented by subclasses to return a list
        of ``SoftwareVersion`` objects on the local filesystem.

        Typical implementations will use functionality such as ``glob`` to
        locate all versions and variations of executables on disk and then
        creating ``SoftwareVersion`` objects for each executable. This method
        is called by the ``get_supported_software()`` method, and each
        ``SoftwareVersion`` object returned is checked against the launcher's
        lists of supported version and product variations via the
        ``_is_supported`` method.
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

    def get_supported_software(self):
        """
        Performs a search for supported software installations.

        This method can be overridden by a subclass to completely override
        supported software discovery. The typical requirement, however, is for
        a subclasses to simply implement the ``_scan_software()`` abstract
        method to return all variations of the software on the local filesystem.

        The default implementation calls ``_scan_software()`` to return
        a list of ``SoftwareVersion`` objects, then calls ``_is_supported()`` on
        each to determine the final list of supported executables.
        """

        software_versions = []

        # retrieve a list of SoftwareVersion objects for all executables
        for sw_version in self._scan_software():
            (supported, reason) = self._is_supported(sw_version)
            if supported:
                self.logger.debug("Accepting %s" % (sw_version,))
                software_versions.append(sw_version)
            else:
                self.logger.debug(
                    "Rejecting %s. Reason: %s" % (sw_version, reason))
                continue

        return software_versions

    ##########################################################################################
    # protected methods

    def _is_supported(self, sw_version):
        """
        Inspects the supplied :class:`SoftwareVersion` object to see if it
        aligns with this launcher's known product and version limitations. Will
        check the :meth:`~minimum_supported_version` as well as the list of
        product and version filters.

        :param sw_version: :class:`SoftwareVersion` object to test against the
            launcher's product and version limitations.

        :returns: A tuple of the form: ``(bool, str)`` where the first item
            is a boolean indicating whether the supplied ``SoftwareVersion`` is
            supported or not. The second argument is ``""`` if supported, but if
            not supported will be a string representing the reason the support
            check failed.

        This method can be used by subclasses that override the
        ``get_supported_software`` method.

        The method can be overridden by subclasses that require more
        sophisticated ``SoftwareVersion`` support checks. Alternatively, the
        ``get_supported_software`` can implement its own support checks using
        the more specific convenience methods ``_is_version_supported`` and
        ``_is_product_supported``, the properties ``products`` and ``versions``,
        or by implementing custom logic.
        """

        # check version support
        if not self._is_version_supported(sw_version.version):
            return (False,
                "Executable '%s' not supported. Failed version check. "
                "(%s not in %s or is older than %s)" % (
                    sw_version.path,
                    sw_version.version,
                    self.versions,
                    self.minimum_supported_version
                )
            )

        # check products list
        if not self._is_product_supported(sw_version.product):
            return (False,
                "Executable '%s' not supported. Failed product check. "
                "(%s not in %s)" % (
                    sw_version.path,
                    sw_version.product,
                    self.products
                )
            )

        # passed all checks. must be supported!
        return (True, "")

    def _is_version_supported(self, version):
        """
        Returns ``True`` if the supplied version string is supported by the
        launcher, ``False`` otherwise.

        The method first checks against the minimum supported version. If the
        supplied version is greater it then checks to ensure that it is in the
        launcher's ``versions`` constraint. If there are no constraints on the
        versions, the method will return ``True``.

        :param str version: A string representing the version to check against.

        :return: Boolean indicating if the supplied version string is supported.

        This method can be overridden in subclasses that require more
        sophisticated version support checks. Note: this method is used by
        ``_is_supported()`` to check version support for the supplied
        ``SoftwareVersion``.
        """

        # first, compare against the minimum version
        min_version = self.minimum_supported_version
        if min_version and is_version_older(version, min_version):
            # the version is older than the minimum supported version
            return False

        if not self.versions:
            # No version restriction. All versions supported
            return True

        # check versions list
        return version in self.versions

    def _is_product_supported(self, product):
        """
        Returns ``True`` if the supplied product name string is supported by the
        launcher, ``False`` otherwise.

        The method checks to ensure that the product name is in the launcher's
        ``products`` constraint. If there are no constraints on the products,
        the method will return ``True``.

        :param str product: A string representing the product name to check
            against.

        :return: Boolean indicating if the supplied product name string is
            supported.

        This method can be overridden in subclasses that require more
        sophisticated product name support checks. Note: this method is used by
        ``_is_supported()`` to check product name support for the supplied
        ``SoftwareVersion``.
        """

        if not self.products:
            # No product restriction. All product variations are supported
            return True

        # check products list
        return product in self.products


class SoftwareVersion(object):
    """
    Container class that stores properties of a DCC that
    are useful for Toolkit Engine Startup functionality.
    """
    def __init__(self, version, product, path, icon=None, arguments=None):
        """
        Constructor.

        :param str version: Explicit version of the DCC represented
                            (e.g. 2017)
        :param str product: Explicit product name of the DCC represented
                            (e.g. "Houdini Apprentice")
        :param str path: Full path to the DCC executable.
        :param str icon: (optional) Full path to a 256x256 (or smaller)
                         png file to use for graphical displays of
                         this SoftwareVersion.
        :param list arguments: (optional) List of command line arguments
                               that need to be passed down to the DCC.
        """
        self._version = version
        self._product = product
        self._path = path
        self._icon_path = icon
        self._arguments = arguments or []

    def __repr__(self):
        """
        Returns unique str representation of the software version
        """
        return "<SoftwareVersion 0x%08x: %s %s, path: %s>" % (
            id(self),
            self.product,
            self.version,
            self.path
        )

    @property
    def version(self):
        """
        An explicit version of the DCC represented by this SoftwareVersion.

        :returns: String version
        """
        return self._version

    @property
    def product(self):
        """
        An explicit product name for the DCC represented by this Software
        Version. Example: "Houdini FX"

        :return: String product name
        """

        return self._product

    @property
    def display_name(self):
        """
        Name to use for this SoftwareVersion in graphical displays.

        :returns: String display name, a combination of the product and version.
        """
        return "%s %s" % (self.product, self.version)

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

    @property
    def arguments(self):
        """
        Command line arguments required to launch the DCC.

        :returns: List of string arguments.
        """
        return self._arguments


class LaunchInformation(object):
    """
    Stores blueprints for how to launch a specific DCC.
    """
    def __init__(self, path=None, args=None, environ=None):
        """
        Constructor

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
