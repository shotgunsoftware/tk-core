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
        self._pipeline_configuration_name = constants.PRIMARY_PIPELINE_CONFIG_NAME
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
        The pipeline configuration that is being operated on.
        By default, the primary pipeline config will be used.
        """
        return self._pipeline_configuration_name

    def _set_pipeline_configuration(self, name):
        """
        The pipeline configuration that is being operated on.
        By default, the primary pipeline config will be used.
        """
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

        # @todo - maybe here we can add support for environment variables in the
        #         future so that studios can easily add their own 'primed cache'
        #         locations for performance or to save space.
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
        Create an sgtk instance for the given project or site,
        then launch into the given engine.

        If entity is None, the method will bootstrap into the site
        config. This method will attempt to resolve the config according
        to business logic set in the associated resolver class and based
        on this launch a configuration. This may involve downloading new
        apps from the toolkit app store and installing files on disk.

        Please note that the API version of the tk instance that hosts
        the engine may not be the same as the API version that was
        executed during the bootstrap.

        :param entity: Shotgun entity to launch engine for
        :type entity: Dictionary with keys type and id
        :param engine_name: name of engine to launch (e.g. ``tk-nuke``)
        :returns: :class:`sgtk.platform.Engine` instance
        """
        log.info("Bootstrapping into engine %s for entity %s." % (engine_name, entity))

        log.debug("Bootstrapping into environment.")
        tk = self._bootstrap_sgtk(engine_name, entity)

        log.debug("Resolving context.")
        if entity is None:
            ctx = tk.context_empty()
        else:
            ctx = tk.context_from_entity_dictionary(entity)

        self._report_progress("Launching Engine...")
        log.debug("Attempting to start engine %s for context %r" % (engine_name, ctx))

        # perform absolute import to ensure we get the new swapped core.
        import tank
        engine = tank.platform.start_engine(engine_name, tk, ctx)

        log.debug("Launched engine %r" % engine)
        return engine


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

        self._report_progress("Resolving Toolkit Context...")
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
        self._report_progress("Resolving configuration...")

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
            config = resolver.resolve_shotgun_configuration(
                self._pipeline_configuration_name,
                self._base_config_descriptor,
                self._sg_connection
            )

        else:
            # fixed resolve based on the base config alone
            # do the full resolve where we connect to shotgun etc.
            config = resolver.resolve_configuration(
                self._base_config_descriptor,
                self._sg_connection,
            )

        # see what we have locally
        self._report_progress("Checking if config is out of date...")
        status = config.status()

        self._report_progress("Updating configuration...")
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
        self._report_progress("Starting up Toolkit...")
        tk = config.get_tk_instance(self._sg_user)

        if status != Configuration.LOCAL_CFG_UP_TO_DATE:
            self._cache_apps(tk)

        return tk

    def _report_progress(self, message, curr_idx=None, max_idx=None):
        """
        Helper method. Report progress back to
        any defined progress callback.

        :param message: Message to report
        :param curr_idx: Optional integer denoting progress. This number is
                         relative to the max_idx which denotes completion
                         of the current task or subtask.
        :param max_idx: Max number of items.
        """
        log.info("Progress Report: %s" % message)
        if self._progress_cb:
            self._progress_cb(message, curr_idx, max_idx)

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
                self._report_progress("Downloading %s..." % descriptor, idx, len(descriptors))
                descriptor.download_local()

            else:
                log.debug("Item %s is already locally installed." % descriptor)

        # pass 3 - do post install
        if do_post_install:
            for descriptor in descriptors:
                self._report_progress("Running post install for %s" % descriptor)
                descriptor.ensure_shotgun_fields_exist(tk)
                descriptor.run_post_install(tk)

