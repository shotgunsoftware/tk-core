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

from . import constants
from .errors import TankBootstrapError
from .configuration import Configuration
from .resolver import ConfigurationResolver
from ..authentication import ShotgunAuthenticator
from .. import LogManager

log = LogManager.get_logger(__name__)

class ToolkitManager(object):
    """
    This class allows for flexible and non-obtrusive management of toolkit configurations
    and installations.
    """

    # Constants used to indicate that the manager is:
    # - bootstrapping the toolkit (with method _bootstrap_sgtk),
    # - starting up the engine (with method _start_engine).
    (TOOLKIT_BOOTSTRAP_PHASE, ENGINE_STARTUP_PHASE) = range(2)

    def __init__(self, sg_user=None):
        """
        :param sg_user: Authenticated Shotgun User object. If you pass in None,
                        the manager will provide a standard authentication for you
                        via the shotgun authentication module and prompting the user
                        if necessary. If you have special requirements around
                        authentication, simply construct an explicit user object
                        and pass it in.
        :type sg_user: :class:`~sgtk.authentication.ShotgunUser`
        """
        if sg_user is None:
            # request a user from the auth module
            sg_auth = ShotgunAuthenticator()
            self._sg_user = sg_auth.get_user()
        else:
            self._sg_user = sg_user

        self._sg_connection = self._sg_user.create_sg_connection()

        # defaults
        self._bundle_cache_fallback_paths = []
        self._pipeline_configuration_name = None
        self._base_config_descriptor = None
        self._progress_cb = None
        self._do_shotgun_config_lookup = True
        self._plugin_id = None

        log.debug("%s instantiated" % self)


    def __repr__(self):
        repr  = "<TkManager "
        repr += " User %s\n" % self._sg_user
        repr += " Cache fallback path %s\n" % self._bundle_cache_fallback_paths
        repr += " Plugin id %s\n" % self._plugin_id
        repr += " Config %s\n" % self._pipeline_configuration_name
        repr += " Base %s >" % self._base_config_descriptor
        return repr

    def _get_pipeline_configuration(self):
        """
        The pipeline configuration that is should be operated on.

        By default, this value is set to ``None``, indicating to the Manager
        that it should attempt to find the most suitable Shotgun pipeline configuration
        given the project and plugin id. In this case, it will look for all pipeline
        configurations associated with the project who are associated with the current
        user. If no user-tagged pipeline configuration exists, it will look for
        the primary configuration, and in case this is not found, it will fall back on the
        :meth:`base_configuration`. If you don't want this check to be carried out in
        Shotgun, please set :meth:`do_shotgun_config_lookup` to False.

        Alternatively, you can set this to a specific pipeline configuration. In that
        case, the Manager will look for a pipeline configuration that matches that name
        and the associated project and plugin id. If such a config cannot be found in
        Shotgun, it falls back on the :meth:`base_configuration`.
        """
        return self._pipeline_configuration_name

    def _set_pipeline_configuration(self, name):
        self._pipeline_configuration_name = name

    pipeline_configuration = property(_get_pipeline_configuration, _set_pipeline_configuration)


    def _get_do_shotgun_config_lookup(self):
        """
        Flag to indicate if the bootstrap process should connect to
        Shotgun and attempt to resolve a config. Defaults to True.

        If ``True``, the bootstrap process will connect to Shotgun as part
        of the startup, look for a pipeline configuration and attempt
        to resolve a toolkit environment to bootstrap into via the
        Pipeline configuration data. Failing this, it will fall back on
        the :meth:`base_configuration`.

        If ``False``, no Shotgun lookup will happen. Instead, whatever config
        is defined via :meth:`base_configuration` will always be used.
        """
        return self._do_shotgun_config_lookup

    def _set_do_shotgun_config_lookup(self, status):
        # setter for do_shotgun_config_lookup
        self._do_shotgun_config_lookup = status

    do_shotgun_config_lookup = property(_get_do_shotgun_config_lookup, _set_do_shotgun_config_lookup)

    def _get_plugin_id(self):
        """
        The Plugin Id is a string that defines the scope of the bootstrap operation.

        If you are bootstrapping into an entire Toolkit pipeline, e.g
        a traditional Toolkit setup, this should be left at its default ``None`` value.

        If you are writing a plugin that is intended to run side by
        side with other plugins in your target environment, the entry
        point will be used to define a scope and sandbox in which your
        plugin will execute.

        When constructing a plugin id for an integration the following
        should be considered:

        - Plugin Ids should uniquely identify the plugin.
        - The name should be short and descriptive.

        We recommend a Plugin Id naming convention of ``service.dcc``,
        for example:

        - A review plugin running inside RV: ``review.rv``.
        - A basic set of pipeline tools running inside of Nuke: ``basic.nuke``
        - A plugin containg a suite of motion capture tools for maya: ``mocap.maya``

        Please make sure that your Plugin Id is **unique, explicit and short**.
        """
        return self._plugin_id

    def _set_plugin_id(self, plugin_id):
        # setter for plugin_id
        self._plugin_id = plugin_id

    plugin_id = property(_get_plugin_id, _set_plugin_id)

    # backwards compatibility
    entry_point = plugin_id

    def _get_base_configuration(self):
        """
        The descriptor (string or dict) for the
        configuration that should be used as a base fallback
        to be used whenever runtime and shotgun configuration
        resolution doesn't resolve an override configuration to use.
        """
        return self._base_config_descriptor

    def _set_base_configuration(self, descriptor):
        # setter for base_configuration
        self._base_config_descriptor = descriptor

    base_configuration = property(_get_base_configuration, _set_base_configuration)

    def _get_bundle_cache_fallback_paths(self):
        """
        Specifies a list of fallback paths where toolkit will go
        look for cached bundles in case a bundle isn't found in
        the primary app cache.

        This is useful if you want to distribute a pre-baked
        package, containing all the app version that a user needs.
        This avoids downloading anything from the app store or other
        sources.

        Any missing bundles will be downloaded and cached into
        the *primary* bundle cache.
        """
        return self._bundle_cache_fallback_paths

    def _set_bundle_cache_fallback_paths(self, paths):
        # setter for bundle_cache_fallback_paths
        self._bundle_cache_fallback_paths = paths

    bundle_cache_fallback_paths = property(
        _get_bundle_cache_fallback_paths,
        _set_bundle_cache_fallback_paths
    )

    def _get_progress_callback(self):
        """
        Callback function property to call whenever progress of the bootstrap should be reported back.

        This function should have the following signature::

            def progress_callback(progress_value, message):
                '''
                Called whenever toolkit reports progress.

                :param progress_value: The current progress value as float number.
                                       values will be reported in incremental order
                                       and always in the range 0.0 to 1.0
                :param message:        Progress message string
                '''
        """
        return self._progress_cb or self._default_progress_callback

    def _set_progress_callback(self, value):
        # Setter for progress_callback.
        self._progress_cb = value

    progress_callback = property(_get_progress_callback, _set_progress_callback)

    def set_progress_callback(self, progress_callback):
        """
        Sets the function to call whenever progress of the bootstrap should be reported back.

        .. note:: This is a deprecated method. Property ``progress_callback`` should now be used.

        :param progress_callback: Callback function that reports back on the toolkit and engine bootstrap progress.
        """

        self.progress_callback = progress_callback

    def bootstrap_engine(self, engine_name, entity=None):
        """
        Create an :class:`~sgtk.Sgtk` instance for the given engine and entity,
        then launch into the given engine.

        The whole engine bootstrap logic will be executed synchronously in the main application thread.

        If entity is None, the method will bootstrap into the site
        config. This method will attempt to resolve the config according
        to business logic set in the associated resolver class and based
        on this launch a configuration. This may involve downloading new
        apps from the toolkit app store and installing files on disk.

        Please note that the API version of the tk instance that hosts
        the engine may not be the same as the API version that was
        executed during the bootstrap.

        :param engine_name: Name of engine to launch (e.g. ``tk-nuke``).
        :param entity: Shotgun entity to launch engine for.
        :type entity: Dictionary with keys ``type`` and ``id``, or ``None`` for the site.
        :returns: :class:`~sgtk.platform.Engine` instance.
        """
        self._log_startup_message(engine_name, entity)

        tk = self._bootstrap_sgtk(engine_name, entity)

        engine = self._start_engine(tk, engine_name, entity)

        return engine

    def bootstrap_engine_async(self,
                               engine_name,
                               entity=None,
                               completed_callback=None,
                               failed_callback=None):
        """
        Create an :class:`~sgtk.Sgtk` instance for the given engine and entity,
        then launch into the given engine.

        This method launches the bootstrap process and returns immediately.
        The :class:`~sgtk.Sgtk` instance will be bootstrapped asynchronously in a background thread,
        followed by launching the engine synchronously in the main application thread.
        This will allow the main application to continue its execution and
        remain responsive when bootstrapping the toolkit involves downloading files and
        installing apps from the toolkit app store.

        If entity is None, the method will bootstrap into the site
        config. This method will attempt to resolve the config according
        to business logic set in the associated resolver class and based
        on this launch a configuration. This may involve downloading new
        apps from the toolkit app store and installing files on disk.

        Two callback functions can be provided.

        A callback function that handles cleanup after successful completion of the bootstrap
        with the following signature::

            def completed_callback(engine):
                '''
                Called by the asynchronous bootstrap upon completion.

                :param engine: Engine instance representing the engine
                               that was launched.
                '''

        A callback function that handles cleanup after failed completion of the bootstrap
        with the following signature::

            def failed_callback(phase, exception):
                '''
                Called by the asynchronous bootstrap if an exception is raised.

                :param phase: Indicates in which phase of the bootstrap the exception
                              was raised. An integer constant which is either
                              ToolkitManager.TOOLKIT_BOOTSTRAP_PHASE or
                              ToolkitManager.ENGINE_STARTUP_PHASE. The former if the
                              failure happened while the system was still bootstrapping
                              and the latter if the system had switched over into the
                              Toolkit startup phase. At this point, the running core API
                              instance may have been swapped over to another version than
                              the one that was originally loaded and may need to be reset
                              in an implementation of this callback.

                :param exception: The python exception that was raised.
                '''

        :param engine_name: Name of engine to launch (e.g. ``tk-nuke``).
        :param entity: Shotgun entity to launch engine for.
        :type entity: Dictionary with keys ``type`` and ``id``, or ``None`` for the site.
        :param completed_callback: Callback function that handles cleanup after successful completion of the bootstrap.
        :param failed_callback: Callback function that handles cleanup after failed completion of the bootstrap.
        """
        self._log_startup_message(engine_name, entity)

        log.debug("Will attempt to start up asynchronously.")

        if completed_callback is None:
            completed_callback = self._default_completed_callback

        if failed_callback is None:
            failed_callback = self._default_failed_callback

        try:
            from .async_bootstrap import AsyncBootstrapWrapper
        except ImportError:
            AsyncBootstrapWrapper = None
            log.warning("Cannot bootstrap asynchronously in a background thread;"
                        " falling back on synchronous startup.")

        if AsyncBootstrapWrapper:

            # Bootstrap an Sgtk instance asynchronously in a background thread,
            # followed by launching the engine synchronously in the main application thread.

            self._bootstrapper = AsyncBootstrapWrapper(self, engine_name, entity, completed_callback, failed_callback)
            self._bootstrapper.bootstrap()

        else:

            # Since Qt is not available, fall back on synchronous bootstrapping.
            # Execute the whole engine bootstrap logic synchronously in the main application thread,
            # while still calling the provided callbacks in order for the caller to work as expected.

            try:

                tk = self._bootstrap_sgtk(engine_name, entity)

            except Exception, exception:

                # Handle cleanup after failed completion of the toolkit bootstrap.
                failed_callback(self.TOOLKIT_BOOTSTRAP_PHASE, exception)

                return

            try:

                engine = self._start_engine(tk, engine_name, entity)

            except Exception, exception:

                # Handle cleanup after failed completion of the engine startup.
                failed_callback(self.ENGINE_STARTUP_PHASE, exception)

                return

            # Handle cleanup after successful completion of the engine bootstrap.
            completed_callback(engine)

    def _log_startup_message(self, engine_name, entity):
        """
        Helper method that logs information about the current session
        :param engine_name: Name of the engine used to bootstrap
        :param entity: Shotgun entity to bootstrap into.
        """
        log.debug("-----------------------------------------------------------------")
        log.debug("Begin bootstrapping Toolkit.")
        log.debug("")
        log.debug("Plugin Id: %s" % self._plugin_id)

        if self._do_shotgun_config_lookup:
            log.debug("Will connect to Shotgun to look for overrides.")
            log.debug("If no overrides found, this config will be used: %s" % self._base_config_descriptor)

            if self._pipeline_configuration_name:
                log.debug("Potential config overrides will be pulled ")
                log.debug("from pipeline config '%s'" % self._pipeline_configuration_name)
            else:
                log.debug("The system will automatically determine the pipeline configuration")
                log.debug("based on the current project id and user.")

        else:
            log.debug("Will not connect to shotgun to resolve config overrides.")
            log.debug("The following config will be used: %s" % self._base_config_descriptor)

        log.debug("")
        log.debug("Target entity for runtime context: %s" % entity)
        log.debug("Bootstrapping engine %s." % engine_name)
        log.debug("-----------------------------------------------------------------")

    def _bootstrap_sgtk(self, engine_name, entity, progress_callback=None):
        """
        Create an sgtk instance for the given engine and entity.

        If entity is None, the method will bootstrap into the site
        config. This method will attempt to resolve the config according
        to business logic set in the associated resolver class and based
        on this launch a configuration. This may involve downloading new
        apps from the toolkit app store and installing files on disk.

        Please note that the API version of the tk instance that hosts
        the engine may not be the same as the API version that was
        executed during the bootstrap.

        :param engine_name: Name of the engine used to resolve a configuration.
        :param entity: Shotgun entity used to resolve a project context.
        :type entity: Dictionary with keys ``type`` and ``id``, or ``None`` for the site.
        :param progress_callback: Callback function that reports back on the toolkit bootstrap progress.
                                  Set to ``None`` to use the default callback function.
        :returns: Bootstrapped :class:`~sgtk.Sgtk` instance.
        """
        if progress_callback is None:
            progress_callback = self.progress_callback

        self._report_progress(progress_callback, 0.0, "Resolving project...")
        if entity is None:
            project_id = None

        elif entity.get("type") == "Project":
            project_id = entity["id"]

        elif "project" in entity and entity["project"].get("type") == "Project":
            # user passed a project link
            project_id = entity["project"]["id"]

        else:
            # resolve from shotgun
            data = self._sg_connection.find_one(
                entity["type"],
                [["id", "is", entity["id"]]],
                ["project"]
            )

            if not data or not data.get("project"):
                raise TankBootstrapError("Cannot resolve project for %s" % entity)
            project_id = data["project"]["id"]


        # get an object to represent the business logic for
        # how a configuration location is being determined
        self._report_progress(progress_callback, 0.1, "Resolving configuration...")

        resolver = ConfigurationResolver(
            self._plugin_id,
            engine_name,
            project_id,
            self._bundle_cache_fallback_paths
        )

        # now request a configuration object from the resolver.
        # this object represents a configuration that may or may not
        # exist on disk. We can use the config object to check if the
        # object needs installation, updating etc.
        if constants.CONFIG_OVERRIDE_ENV_VAR in os.environ:
            # an override environment variable has been set. This takes precedence over
            # all other methods and is useful when you do development. For example,
            # if you are developing an app and want to test it with an existing plugin
            # without wanting to rebuild the plugin, simply set this environment variable
            # to point at a local config on disk:
            #
            # TK_BOOTSTRAP_CONFIG_OVERRIDE=/path/to/dev_config
            #
            log.info("Detected a %s environment variable." % constants.CONFIG_OVERRIDE_ENV_VAR)
            config_override_path = os.environ[constants.CONFIG_OVERRIDE_ENV_VAR]
            # resolve env vars and tildes
            config_override_path = os.path.expanduser(os.path.expandvars(config_override_path))
            log.info("Config override set to '%s'" % config_override_path)

            if not os.path.exists(config_override_path):
                raise TankBootstrapError(
                    "Cannot find config '%s' defined by override env var %s." % (
                        config_override_path,
                        constants.CONFIG_OVERRIDE_ENV_VAR
                    )
                )

            config = resolver.resolve_configuration(
                {"type": "dev", "path": config_override_path},
                self._sg_connection,
            )

        elif self._do_shotgun_config_lookup:
            # do the full resolve where we connect to shotgun etc.
            log.debug("Checking for pipeline configuration overrides in Shotgun.")
            log.debug("In order to turn this off, set do_shotgun_config_lookup to False")
            config = resolver.resolve_shotgun_configuration(
                self._pipeline_configuration_name,
                self._base_config_descriptor,
                self._sg_connection,
                self._sg_user.login
            )

        else:
            # fixed resolve based on the base config alone
            # do the full resolve where we connect to shotgun etc.
            config = resolver.resolve_configuration(
                self._base_config_descriptor,
                self._sg_connection,
            )

        log.info("Using %s" % config)
        log.debug("Bootstrapping into configuration %r" % config)

        # see what we have locally
        status = config.status()

        self._report_progress(progress_callback, 0.2, "Updating configuration...")
        if status == Configuration.LOCAL_CFG_UP_TO_DATE:
            log.info("Your locally cached configuration is up to date.")

        elif status == Configuration.LOCAL_CFG_MISSING:
            log.info("A locally cached configuration will be set up.")
            config.update_configuration()

        elif status == Configuration.LOCAL_CFG_DIFFERENT:
            log.info("Your locally cached configuration differs and will be updated.")
            config.update_configuration()

        elif status == Configuration.LOCAL_CFG_INVALID:
            log.info("Your locally cached configuration looks invalid and will be replaced.")
            config.update_configuration()

        else:
            raise TankBootstrapError("Unknown configuration update status!")

        # we can now boot up this config.
        self._report_progress(progress_callback, 0.3, "Starting up Toolkit...")
        tk = config.get_tk_instance(self._sg_user)

        if status != Configuration.LOCAL_CFG_UP_TO_DATE:
            self._cache_apps(tk, progress_callback)

        return tk

    def _start_engine(self, tk, engine_name, entity, progress_callback=None):
        """
        Launch into the given engine.

        If entity is None, the method will bootstrap into the site config.

        Please note that the API version of the tk instance that hosts
        the engine may not be the same as the API version that was
        executed during the bootstrap.

        :param tk: Bootstrapped :class:`~sgtk.Sgtk` instance.
        :param engine_name: Name of the engine to start up.
        :param entity: Shotgun entity used to resolve a project context.
        :type entity: Dictionary with keys ``type`` and ``id``, or ``None`` for the site.
        :param progress_callback: Callback function that reports back on the engine startup progress.
                                  Set to ``None`` to use the default callback function.
        :returns: Started :class:`~sgtk.platform.Engine` instance.
        """

        log.debug("Begin starting up engine %s." % engine_name)

        if progress_callback is None:
            progress_callback = self.progress_callback

        self._report_progress(progress_callback, 0.8, "Resolving context...")
        if entity is None:
            ctx = tk.context_empty()
        else:
            ctx = tk.context_from_entity_dictionary(entity)

        self._report_progress(progress_callback, 0.9, "Launching Engine...")
        log.debug("Attempting to start engine %s for context %r" % (engine_name, ctx))

        # perform absolute import to ensure we get the new swapped core.
        import tank
        engine = tank.platform.start_engine(engine_name, tk, ctx)

        log.debug("Launched engine %r" % engine)

        return engine

    def _report_progress(self, progress_callback, progress_value, message):
        """
        Helper method that reports back on the bootstrap progress to a defined progress callback.

        :param progress_callback: Callback function to use to report back.
        :param progress_value: Current progress value, a float number ranging from 0.0 to 1.0
                               representing the percentage of work completed.
        :param message: Progress message string to report.
        """

        log.info("Progress Report (%s%%): %s" % (int(progress_value*100), message))

        try:
            # Call the new style progress callback.
            progress_callback(progress_value, message)
        except TypeError:
            # Call the old style progress callback with signature (message, current_index, maximum_index).
            progress_callback(message, None, None)

    def _is_toolkit_activated_in_shotgun(self):
        """
        Checks if toolkit has been activated in sg.

        :return: True if true, false otherwise
        """
        log.debug("Checking if Toolkit is enabled in Shotgun...")
        entity_types = self._sg_connection.schema_entity_read()
        # returns a dict keyed by entity type
        enabled = constants.PIPELINE_CONFIGURATION_ENTITY_TYPE in entity_types
        log.debug("...enabled: %s" % enabled)
        return enabled

    def _cache_apps(self, tk, progress_callback, do_post_install=False):
        """
        Caches all apps associated with the given toolkit instance.

        :param tk: Bootstrapped :class:`~sgtk.Sgtk` instance to cache items for.
        :param progress_callback: Callback function that reports back on the engine startup progress.
        :param do_post_install: Set to true to execute the post install triggers.
        """

        log.info("Downloading and installing apps...")

        # each entry in the config template contains instructions about which version of the app
        # to use. First loop over all environments and gather all descriptors we should download,
        # then go ahead and download and post-install them
        pc = tk.pipeline_configuration

        # pass 1 - populate list of all descriptors
        descriptors = []
        for env_name in pc.get_environments():

            env_obj = pc.get_environment(env_name)

            for engine in env_obj.get_engines():
                descriptors.append(env_obj.get_engine_descriptor(engine))

                for app in env_obj.get_apps(engine):
                    descriptors.append(env_obj.get_app_descriptor(engine, app))

            for framework in env_obj.get_frameworks():
                descriptors.append(env_obj.get_framework_descriptor(framework))

        # pass 2 - download all apps
        for idx, descriptor in enumerate(descriptors):

            # Scale the progress step 0.3 between this value 0.4 and the next one 0.7
            # to compute a value progressing while looping over the indexes.
            progress_value = 0.4 + idx * (0.3 / len(descriptors))

            if not descriptor.exists_local():
                message = "Downloading %s (%s of %s)..." % (descriptor, idx+1, len(descriptors))
                self._report_progress(progress_callback, progress_value, message)
                descriptor.download_local()
            else:
                message = "%s already installed locally (%s of %s)." % (descriptor, idx+1, len(descriptors))
                self._report_progress(progress_callback, progress_value, message)

        # pass 3 - do post install
        if do_post_install:
            for descriptor in descriptors:
                self._report_progress(progress_callback, 0.7, "Running post install for %s" % descriptor)
                descriptor.ensure_shotgun_fields_exist(tk)
                descriptor.run_post_install(tk)

    def _default_progress_callback(self, progress_value, message):
        """
        Default callback function that reports back on the toolkit and engine bootstrap progress.

        :param progress_value: Current progress value, ranging from 0.0 to 1.0.
        :param message: Progress message to report.
        """

        log.debug("Default progress callback (%s): %s" % (progress_value, message))

    def _default_completed_callback(self, engine):
        """
        Default callback function that handles cleanup after successful completion of the bootstrap.

        :param engine: Launched :class:`sgtk.platform.Engine` instance.
        """

        log.debug("Default completed callback: %s" % engine.instance_name)

    def _default_failed_callback(self, phase, exception):
        """
        Default callback function that handles cleanup after failed completion of the bootstrap.

        :param phase: Bootstrap phase that raised the exception,
                      ``ToolkitManager.TOOLKIT_BOOTSTRAP_PHASE`` or ``ToolkitManager.ENGINE_STARTUP_PHASE``.
        :param exception: Python exception raised while bootstrapping.
        """

        phase_name = "TOOLKIT_BOOTSTRAP_PHASE" if phase == self.TOOLKIT_BOOTSTRAP_PHASE else "ENGINE_STARTUP_PHASE"

        log.debug("Default failed callback (%s): %s" % (phase_name, exception))
