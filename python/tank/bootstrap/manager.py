# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

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

    # Used to indicate that the manager is bootstrapping the toolkit (with method _bootstrap_sgtk).
    TOOLKIT_BOOTSTRAP_PHASE = "sgtk"

    # Used to indicate that the manager is starting the engine (with method _start_engine).
    ENGINE_STARTUP_PHASE = "engine"

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
        self._entry_point = None

        log.debug("%s instantiated" % self)


    def __repr__(self):
        repr  = "<TkManager "
        repr += " User %s\n" % self._sg_user
        repr += " Cache fallback path %s\n" % self._bundle_cache_fallback_paths
        repr += " Config %s\n" % self._pipeline_configuration_name
        repr += " Base %s >" % self._base_config_descriptor
        return repr

    def _get_pipeline_configuration(self):
        """
        The pipeline configuration that is should be operated on.

        By default, this value is set to ``None``, indicating to the Manager
        that it should attempt to find the most suitable Shotgun pipeline configuration
        given the project and entry point. In this case, it will look for all pipeline
        configurations associated with the project who are associated with the current
        user. If no user-tagged pipeline configuration exists, it will look for
        the primary configuration, and in case this is not found, it will fall back on the
        :meth:`base_configuration`. If you don't want this check to be carried out in
        Shotgun, please set :meth:`do_shotgun_config_lookup` to False.

        Alternatively, you can set this to a specific pipeline configuration. In that
        case, the Manager will look for a pipeline configuration that matches that name
        and the associated project and entry point. If such a config cannot be found in
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


    def _get_entry_point(self):
        """
        The entry point defines the scope of the bootstrap operation.

        If you are bootstrapping into an entire Toolkit pipeline, e.g
        a traditional Toolkit setup, this should be left blank.

        If you are writing a plugin that is intended to run side by
        side with other plugins in your target environment, the entry
        point will be used to define a scope and sandbox in which your
        plugin will execute.

        In the future, it will be possible to use the entry point value
        to customize the behavior of a
        plugin via Shotgun. At bootstrap, toolkit will look for a pipeline
        configuration with a matching name and entry point. If found, this
        will be used instead of the one defined by the :meth:`base_configuration`
        property.

        It is possible for multiple plugins running in different DCCs
        to share the same entry point - in this case, they would all
        get their settings and setup from a shared configuration. If you
        were to override the base configuration in Shotgun, your override
        would affect the entire suite of plugins. This kind of setup allows
        for the development of several plugins in different DCCs that together
        form a curated workflow.

        We recommend an entry point naming convention of ``provider_service``,
        for example:

        - A plugin maintained by the RV group which handles review inside RV would
          be named ``rv_review``.
        - A plugin for a toolkit load/publish workflow that runs inside of Maya and
          Nuke, maintained by the Toolkit team, could be named ``sgtk_publish``.
        - A plugin containg a studio VR workflow across multiple DCCs could be
          named ``studioname_vrtools``.

        Please make sure that your entry point is **unique, explicit and short**.

            .. note:: If you want to force the :meth:`base_configuration` to always
                      be used, set :meth:`do_shotgun_config_lookup` to False.
        """
        return self._entry_point

    def _set_entry_point(self, entry_point):
        # setter for entry_point
        self._entry_point = entry_point

    entry_point = property(_get_entry_point, _set_entry_point)

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


    def set_progress_callback(self, callback):
        """
        Specify a method to call whenever progress should be reported back.

        The method needs to have the following signature::

            progress_callback(message, current_index, max_index)

        The two index parameters are used to illustrate progress
        over time and looping. ``max_index`` is the total number of
        current progress items, ``current_index`` is the currently
        processed item. This can be used to compute a percentage.
        Note that ``max_index`` may change at any time and is not guaranteed
        to be fixed.

        :param callback: Callback fn. See above for details.
        """
        self._progress_cb = callback

    def bootstrap_engine(self, engine_name, entity=None):
        """
        Create an :class:`sgtk.Sgtk` instance for the given engine and entity,
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
        :returns: :class:`sgtk.platform.Engine` instance.
        """

        log.info("Bootstrapping engine %s for entity %s." % (engine_name, entity))

        tk = self._bootstrap_sgtk(engine_name, entity)

        engine = self._start_engine(tk, engine_name, entity)

        return engine

    def bootstrap_engine_async(self,
                               engine_name,
                               entity=None,
                               progress_callback=None,
                               completed_callback=None,
                               failed_callback=None):
        """
        Create an :class:`sgtk.Sgtk` instance for the given engine and entity,
        then launch into the given engine.

        The :class:`sgtk.Sgtk` instance will be bootstrapped asynchronously in a background thread,
        followed by launching the engine synchronously in the main application thread.
        This will allow the main application to continue its execution and
        remain responsive when bootstrapping the toolkit involves downloading files and
        installing apps from the toolkit app store.

        If entity is None, the method will bootstrap into the site
        config. This method will attempt to resolve the config according
        to business logic set in the associated resolver class and based
        on this launch a configuration. This may involve downloading new
        apps from the toolkit app store and installing files on disk.

        3 callback functions can be provided.

        A callback function that reports back on the bootstrap progress
        with the following signature::

            progress_callback(progress_value, message, current_index, maximum_index)

        where:
        - ``progress_value`` is the current progress value, a float number ranging from 0.0 to 1.0
                             representing the percentage of work completed.
        - ``message`` is the progress message string to report.
        - ``current_index`` is an optional current item number being looped over.
                            This integer number is relative to ``maximum_index``.
                            Its value is ``None`` when not provided.
        - ``maximum_index`` is an optional maximum item number being looped over.
                            This integer number leads to completion of the current progress step.
                            Its value is ``None`` when not provided.

        A callback function that handles cleanup after successful completion of the bootstrap
        with the following signature::

            completed_callback(engine)

        where:
        - ``engine``is the launched :class:`sgtk.platform.Engine` instance.

        A callback function that handles cleanup after failed completion of the bootstrap
        with the following signature::

            failed_callback(phase, exception)

        where:
        - ``phase`` is the bootstrap phase that raised the exception,
                    ``ToolkitManager.TOOLKIT_BOOTSTRAP_PHASE`` or ``ToolkitManager.ENGINE_STARTUP_PHASE``.
                    Using this phase, the callback can decide if the toolkit core needs
                    to be re-imported to ensure usage of a swapped in version.
        - ``exception`` is the python exception raised while bootstrapping.

        Please note that the API version of the tk instance that hosts
        the engine may not be the same as the API version that was
        executed during the bootstrap.

        :param engine_name: Name of engine to launch (e.g. ``tk-nuke``).
        :param entity: Shotgun entity to launch engine for.
        :param progress_callback: Callback function that reports back on the toolkit and engine bootstrap progress.
        :param completed_callback: Callback function that handles cleanup after successful completion of the bootstrap.
        :param failed_callback: Callback function that handles cleanup after failed completion of the bootstrap.
        """

        log.info("Bootstrapping engine %s for entity %s." % (engine_name, entity))

        try:
            import async
        except ImportError:
            async = None
            log.warning("Cannot bootstrap asynchronously in a background thread;"
                        " falling back on synchronous startup.")

        if async:

            # Bootstrap an Sgtk instance asynchronously in a background thread,
            # followed by launching the engine synchronously in the main application thread.

            self._bootstrapper = async.AsyncBootstrapWrapper(self, engine_name, entity)
            self._bootstrapper.set_callbacks(progress_callback, completed_callback, failed_callback)
            self._bootstrapper.bootstrap()

        else:

            # Since Qt is not available, fall back on synchronous bootstrapping.
            # Execute the whole engine bootstrap logic synchronously in the main application thread,
            # while still calling the provided callbacks in order for the caller to work as expected.

            # Install the bootstrap progress reporting callback.
            self.set_progress_callback(progress_callback)

            try:

                tk = self._bootstrap_sgtk(engine_name, entity)

            except Exception, exception:

                if failed_callback:
                    # Handle cleanup after failed completion of the toolkit bootstrap.
                    failed_callback(self.TOOLKIT_BOOTSTRAP_PHASE, exception)

                # Remove the bootstrap progress reporting callback.
                self.set_progress_callback(None)

                return

            try:

                engine = self._start_engine(tk, engine_name, entity)

            except Exception, exception:

                if failed_callback:
                    # Handle cleanup after failed completion of the engine startup.
                    failed_callback(self.ENGINE_STARTUP_PHASE, exception)

                # Remove the bootstrap progress reporting callback.
                self.set_progress_callback(None)

                return

            if completed_callback:
                # Handle cleanup after successful completion of the engine bootstrap.
                completed_callback(engine)

            # Remove the bootstrap progress reporting callback.
            self.set_progress_callback(None)

    def _bootstrap_sgtk(self, engine_name, entity):
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

        :param entity: Shotgun entity to launch engine for
        :param engine_name: name of engine to launch (e.g. tk-nuke)
        :returns: sgtk instance
        """
        log.debug("Begin bootstrapping sgtk.")

        self._report_progress(progress_value=0.0, message="Resolving project...")
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
        self._report_progress(progress_value=0.1, message="Resolving configuration...")

        resolver = ConfigurationResolver(
            self._entry_point,
            engine_name,
            project_id,
            self._bundle_cache_fallback_paths
        )

        # now request a configuration object from the resolver.
        # this object represents a configuration that may or may not
        # exist on disk. We can use the config object to check if the
        # object needs installation, updating etc.

        if self._do_shotgun_config_lookup:
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

        self._report_progress(progress_value=0.2, message="Updating configuration...")
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
        self._report_progress(progress_value=0.3, message="Starting up Toolkit...")
        tk = config.get_tk_instance(self._sg_user)

        if status != Configuration.LOCAL_CFG_UP_TO_DATE:
            self._cache_apps(tk)

        return tk

    def _start_engine(self, tk, engine_name, entity):
        """
        Launch into the given engine.

        If entity is None, the method will bootstrap into the site config.

        Please note that the API version of the tk instance that hosts
        the engine may not be the same as the API version that was
        executed during the bootstrap.

        :param tk: :class:`sgtk.Sgtk` instance
        :param engine_name: name of engine to launch (e.g. ``tk-nuke``)
        :param entity: Shotgun entity to launch engine for
        :returns: :class:`sgtk.platform.Engine` instance
        """

        self._report_progress(progress_value=0.8, message="Resolving context...")
        if entity is None:
            ctx = tk.context_empty()
        else:
            ctx = tk.context_from_entity_dictionary(entity)

        self._report_progress(progress_value=0.9, message="Launching Engine...")
        log.debug("Attempting to start engine %s for context %r" % (engine_name, ctx))

        # perform absolute import to ensure we get the new swapped core.
        import tank
        engine = tank.platform.start_engine(engine_name, tk, ctx)

        log.debug("Launched engine %r" % engine)

        return engine

    def _report_progress(self, progress_value, message, current_index=None, maximum_index=None):
        """
        Helper method that reports back on the bootstrap progress to a defined progress callback.

        :param progress_value: Current progress value, a float number ranging from 0.0 to 1.0
                               representing the percentage of work completed.
        :param message: Progress message string to report.
        :param current_index: Optional current item number being looped over.
                              This integer number is relative to ``maximum_index``.
                              Its value is ``None`` when not provided.
        :param maximum_index: Optional maximum item number being looped over.
                              This integer number leads to completion of the current progress step.
                              Its value is ``None`` when not provided.
        """

        log.info("Progress Report: %s" % message)

        if self._progress_cb:
            try:
                # Call the new style progress callback.
                self._progress_cb(progress_value, message, current_index, maximum_index)
            except TypeError:
                # Call the old style progress callback.
                self._progress_cb(message, current_index, maximum_index)

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

    def _cache_apps(self, tk, do_post_install=False):
        """
        Caches all apps associated with the given tk instance

        :param tk: Toolkit instance to cache items for
        :param do_post_install: Set to true for post install triggers to execute
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

            if not descriptor.exists_local():
                self._report_progress(progress_value=0.4 + idx*(0.3/len(descriptors)),
                                      message="Downloading %s..." % descriptor,
                                      current_index=idx,
                                      maximum_index=len(descriptors)-1)
                descriptor.download_local()

            else:
                log.debug("Item %s is already locally installed." % descriptor)

        # pass 3 - do post install
        if do_post_install:
            for descriptor in descriptors:
                self._report_progress(progress_value=0.7, message="Running post install for %s" % descriptor)
                descriptor.ensure_shotgun_fields_exist(tk)
                descriptor.run_post_install(tk)

