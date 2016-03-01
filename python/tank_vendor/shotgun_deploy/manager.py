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
import sys
import uuid
import datetime
import tempfile

from . import util
from . import zipfilehelper
from . import Descriptor, create_descriptor
from . import constants
from ..shotgun_base import ensure_folder_exists
from .errors import ShotgunDeployError
from .configuration import Configuration, create_managed_configuration
from .resolver import BasicConfigurationResolver
from .io_descriptor import location_dict_to_uri

log = util.get_shotgun_deploy_logger()

class ToolkitManager(object):
    """
    A class that defines toolkit bootstrap operations
    """

    def __init__(self, sg_user):
        """
        Constructor

        :param sg_user: Authenticated Shotgun User object
        """
        self._sg_user = sg_user
        self._sg_connection = self._sg_user.create_sg_connection()

        # defaults
        self._bundle_cache_fallback_paths = []
        self._pipeline_configuration_name = constants.PRIMARY_PIPELINE_CONFIG_NAME
        self._base_config_location = None
        self._namespace = constants.DEFAULT_NAMESPACE
        self._progress_cb = None

    def __repr__(self):
        repr  = "<TkManager "
        repr += " User %s\n" % self._sg_user
        repr += " Cache fallback path %s\n" % self._bundle_cache_fallback_paths
        repr += " Config %s\n" % self._pipeline_configuration_name
        repr += " Namespace: %s\n" % self._namespace
        repr += " Base %s >" % self._base_config_location
        return repr



    def _get_namespace(self):
        """
        Returns the namespace that the manager will bootstrap into.
        Namespaces make it possible to have more than a single pipeline
        configuration for a project/pipeline config name combo. For example,
        you may have primary site configurations for both rv, desktop and maya,
        each with specific apps and settings that can live alongside each other.

        :returns: namespace as string
        """
        return self._namespace

    def _set_namespace(self, namespace):
        """
        Specify a namespace to bootstrap into. Namespaces make it possible
        to have more than a single pipeline configuration for a
        project/pipeline config name combo. For example, you may have primary
        site configurations for both rv, desktop and maya, each with specific
        apps and settings that can live alongside each other.

        :param namespace: name space string, typically one short word,
                          e.g. 'maya', 'rv', 'desktop'
        """
        self._namespace = namespace

    namespace = property(_get_namespace, _set_namespace)



    def _set_pipeline_configuration(self, name):
        """
        Specify a non-default pipeline configuration to operate on.
        By default, the primary config will be used.

        :param name: Pipeline configuration name as string
        """
        self._pipeline_configuration_name = name

    def _get_pipeline_configuration(self):
        """
        Returns the pipeline configuration that is being operated on.
        By default, the primary config will be used.

        :returns: Pipeline configuration name as string
        """
        return self._pipeline_configuration_name

    pipeline_configuration = property(_get_pipeline_configuration, _set_pipeline_configuration)



    def _get_base_configuration(self):
        """
        Returns the location (string or dict) for the
        config that should be used whenever shotgun
        lookups fail.

        :returns: base configuration location, dict, str or None
        """
        return self._base_config_location

    def _set_base_configuration(self, location):
        """
        Specify the location (string or dict) for the
        config that should be used whenever shotgun
        lookups fail.

        :param location: location dictionary or str
        """
        self._base_config_location = location

    base_configuration = property(_get_base_configuration, _set_base_configuration)


    def _set_bundle_cache_fallback_paths(self, paths):
        """
        Specify a list of fallback paths where toolkit will go
        look for cached bundles in case a bundle isn't found in
        the primary app cache.

        This is useful if you want to distribute a pre-baked
        package, containing all the app version that a user needs.
        This avoids downloading anything from the app store or other
        sources.

        Any missing bundles will be downloaded and cached into
        the *primary* bundle cache. For unmanaged projects, this is
        typically a folder on the local machine.

        :param paths: List of paths
        """
        # @todo - maybe here we can add support for environment variables in the
        #         future so that studios can easily add their own 'primed cache'
        #         locations for performance or to save space.
        self._bundle_cache_fallback_paths = paths

    def _get_bundle_cache_fallback_paths(self):
        """
        Returns the list of bundle cache fallback paths.

        :returns: list of path strings
        """
        return self._bundle_cache_fallback_paths

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
        over time and looping. max_index is the total number of
        current progress items, current_index is the currently
        processed item. This can be used to compute a percentage.
        Note that max_index may change at any time and is not guaranteed
        to be fixed.

        :param callback: Callback fn. See above for details.
        """
        self._progress_cb = callback

    def bootstrap_sgtk(self, project_id=None):
        """
        Create an sgtk instance for the given project or site.

        If project_id is None, the method will bootstrap into the site
        config. This method will attempt to resolve the config according
        to business logic set in the assocaited resolver class and based
        on this launch a configuration. This may involve downloading new
        apps from the toolkit app store and installing files on disk.

        Please note that the API version of the tk instance may not
        be the same as the API version that was executed to bootstrap.

        :param project_id: Project to bootstrap into, None for site mode
        :returns: sgtk instance
        """
        log.debug("Begin bootstrapping sgtk.")

        # get an object to represent the business logic for
        # how a configuration location is being determined
        #
        # @todo - in the future, there may be more and/or other
        # resolvers to implement different workflows.
        # For now, this logic is just separated out in a
        # separate file.
        self._report_progress("Resolving configuration...")

        resolver = BasicConfigurationResolver(
            self._sg_connection,
            self._bundle_cache_fallback_paths
        )

        # now request a configuration object from the resolver.
        # this object represents a configuration that may or may not
        # exist on disk. We can use the config object to check if the
        # object needs installation, updating etc.
        config = resolver.resolve_configuration(
            project_id,
            self._pipeline_configuration_name,
            self._namespace,
            self._base_config_location
        )

        # see what we have locally
        self._report_progress("Checking if config is out of date...")
        status = config.status()

        self._report_progress("Updating configuration...")
        if status == Configuration.LOCAL_CFG_UP_TO_DATE:
            log.info("Your configuration is up to date.")

        elif status == Configuration.LOCAL_CFG_MISSING:
            log.info("A brand new configuration will be created locally.")
            config.update_configuration()

        elif status == Configuration.LOCAL_CFG_OLD:
            log.info("Your local configuration is out of date and will be updated.")
            config.update_configuration()

        elif status == Configuration.LOCAL_CFG_INVALID:
            log.info("Your local configuration looks invalid and will be replaced.")
            config.update_configuration()

        else:
            raise ShotgunDeployError("Unknown configuration update status!")

        # we can now boot up this config.
        self._report_progress("Starting up Toolkit...")
        tk = config.get_tk_instance(self._sg_user)

        if status != Configuration.LOCAL_CFG_UP_TO_DATE:
            self._cache_apps(tk)

        return tk

    def bootstrap_engine(self, engine_name, entity=None):
        """
        Convenience method that bootstraps into the given engine.

        Similar to bootstrap_sgtk(), this will configure and install
        items necessary in order to start up toolkit. Once launched,
        the specified engine will be initiated.

        :param entity: Shotgun entity to launch engine for
        :param engine_name: name of engine to launch (e.g. tk-nuke)
        :returns: engine instance
        """
        log.debug("bootstrapping into an engine.")

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
                raise ShotgunDeployError("Cannot resolve project for %s" % entity)
            project_id = data["project"]["id"]

        tk = self.bootstrap_sgtk(project_id)
        log.debug("Bootstrapped into tk instance %r" % tk)

        if entity is None:
            ctx = tk.context_empty()
        else:
            ctx = tk.context_from_entity_dictionary(entity)

        self._report_progress("Launching Engine...")
        log.debug("Attempting to start engine %s for context %r" % (engine_name, ctx))

        # @todo - fix this import
        import tank
        engine = tank.platform.start_engine(engine_name, tk, ctx)

        log.debug("Launched engine %r" % engine)
        return engine

    def get_configuration_uri(self, project_id=None):
        """
        Return the config uri that is associated with the given
        project. Also takes into account the namespace and
        pipeline configuration state of the manager instance itself.

        :param project_id: Project to retrieve configuration uri for.
        :return: toolkit config locator uri string
        """
        resolver = BasicConfigurationResolver(
            self._sg_connection,
            self._bundle_cache_fallback_paths
        )

        # now request a configuration object from the resolver.
        # this object represents a configuration that may or may not
        # exist on disk. We can use the config object to check if the
        # object needs installation, updating etc.
        config = resolver.resolve_configuration(
            project_id,
            self._pipeline_configuration_name,
            self._namespace,
            self._base_config_location
        )

        # return the uri associated with this configuration
        return config.get_descriptor().get_uri()

    ####################################################################################
    # future functionality
    #
    # def validate(self, project_id=None):
    #     """
    #     Check the validity of the given project against the given
    #     base config. This can used to determine that a particular
    #     base config can be assocaited with a given shotgun project.
    #
    #     Checks that storages exists and are correctly named and checks
    #     that a tank project name has been set when necessary.
    #
    #     :param project_id: Project id for which to check
    #     :returns: TBD
    #     """
    #     # @todo - implement validate() method
    #
    # def upload_configuration(self, project_id=None):
    #     """
    #     Convenience method that uploads the given base
    #     config to Shotgun.
    #
    #     :param project_id: Project to upload config to.
    #     """
    #     if not util.is_toolkit_activated_in_shotgun(self._sg_connection):
    #         raise ShotgunDeployError(
    #             "Toolkit has not yet been fully activated in Shotgun! Before you can upload "
    #             "any configurations, you must go into the app management menu in Shotgun "
    #             "and turn on the Toolkit integration.")
    #
    #     # @todo - this method assumes non-official fields on pipelineconfiguration
    #     # so requires further discussion prior to release.
    #
    #     log.debug("Begin uploading config to sgtk.")
    #
    #     # first resolve the config we are going to upload
    #     cfg_descriptor = self._get_base_descriptor()
    #     log.debug("Will upload %s to %r, project %s" % (cfg_descriptor, self, project_id))
    #
    #     # make sure it exists locally
    #     self._report_progress("Downloading configuration...")
    #     cfg_descriptor.ensure_local()
    #
    #     # zip up the config
    #     self._report_progress("Compressing configuration...")
    #     config_root_path = cfg_descriptor.get_path()
    #     log.debug("Zipping up %s" % config_root_path)
    #
    #     zip_tmp = os.path.join(
    #         tempfile.gettempdir(),
    #         "tk_%s" % uuid.uuid4().hex,
    #         datetime.datetime.now().strftime("%Y%m%d_%H%M%S.zip")
    #     )
    #     ensure_folder_exists(os.path.dirname(zip_tmp))
    #     zipfilehelper.zip_file(config_root_path, zip_tmp)
    #
    #     # make sure a pipeline config record exists
    #     self._report_progress("Looking for Pipeline Configuration...")
    #     pc_id = self._ensure_pipeline_config_exists(project_id)
    #
    #     self._report_progress("Uploading zip to Shotgun...")
    #     attachment_id = self._sg_connection.upload(
    #         constants.PIPELINE_CONFIGURATION_ENTITY_TYPE,
    #         pc_id,
    #         zip_tmp,
    #         constants.SHOTGUN_PIPELINECONFIG_ATTACHMENT_FIELD
    #     )
    #     log.debug("Upload complete!")
    #
    #     # write uri
    #     self._report_progress("Updating Pipeline Configuration...")
    #
    #     location = {
    #         "type": "shotgun",
    #         "entity_type": constants.PIPELINE_CONFIGURATION_ENTITY_TYPE,
    #         "name": self._pipeline_configuration_name,
    #         "field": constants.SHOTGUN_PIPELINECONFIG_ATTACHMENT_FIELD,
    #         "project_id": project_id,
    #         "version": attachment_id
    #     }
    #
    #     uri = location_dict_to_uri(location)
    #
    #     log.debug("Updating pipeline config with new uri %s" % uri)
    #     self._sg_connection.update(
    #         constants.PIPELINE_CONFIGURATION_ENTITY_TYPE,
    #         pc_id,
    #         {constants.SHOTGUN_PIPELINECONFIG_URI_FIELD: uri}
    #     )
    #
    #     return pc_id
    #
    # def create_managed_configuration(
    #     self,
    #     project_id,
    #     win_path=None,
    #     mac_path=None,
    #     linux_path=None,
    #     win_python=None,
    #     mac_python=None,
    #     linux_python=None,
    #     use_global_bundle_cache=False
    # ):
    #     """
    #     Creates a managed configuration on disk given the base location.
    #     The configuration will be downloaded and deployed for the
    #     given project. A pipeline configuration will be created with paths referencing
    #     the given locations on disk.
    #
    #     A path to a python interpreter can be specified. If this is not set, the
    #     Shotgun desktop default python path will be used.
    #
    #     This process is akin to the toolkit project setup tank command.
    #
    #     :param project_id: Project id for which to create the configuration
    #     :param win_path: Optional windows install path
    #     :param mac_path: Otional mac install path
    #     :param linux_path: Optional linux install path.
    #     :param win_python: Optional python interpreter path.
    #     :param mac_python: Optional python interpreter path.
    #     :param linux_python: Optional python interpreter path.
    #     :param use_global_bundle_cache: If True, the global bundle cache location
    #         will be used to cache bundles (apps, engine and frameworks. This location
    #         is on the local disk and is shared across all projects and all sites, but
    #         not shared between machines. If set to False, bundles will be cached
    #         in a location relative to the core installation (e.g as part of the
    #         managed configuration). This is synonymous with the way toolkit worked
    #         up to core v0.17. For managed configurations used for development and not
    #         intended to shared between multiple machines, setting this to True is
    #         recommended. For configurations that are deployed to production and shared
    #         between multiple users and machines, it should be set to False.
    #
    #     :return: Shotgun id for the pipeline relevant configuration
    #     """
    #     if not util.is_toolkit_activated_in_shotgun(self._sg_connection):
    #         raise ShotgunDeployError(
    #             "Toolkit has not yet been fully activated in Shotgun! Before you can upload "
    #             "any configurations, you must go into the app management menu in Shotgun "
    #             "and turn on the Toolkit integration.")
    #
    #     log.debug("Begin installing config on disk.")
    #
    #     # check that we have a local path and interpreter
    #     curr_os_path = {"win32": win_path, "linux2": linux_path, "darwin": mac_path}[sys.platform]
    #
    #     if curr_os_path is None:
    #         raise ShotgunDeployError("Need to specify a path for the current operating system!")
    #
    #     # first resolve the config we are going to use to base the project on
    #     descriptor_to_install = self._get_base_descriptor()
    #     log.debug("Configuration will be based on: %r" % descriptor_to_install)
    #
    #     # make sure a pipeline config record exists
    #     self._report_progress("Checking Pipeline Configuration...")
    #     pc_id = self._ensure_pipeline_config_exists(project_id)
    #
    #     # create an object to represent our configuration install
    #     self._report_progress("Installing Configuration...")
    #     config = create_managed_configuration(
    #         self._sg_connection,
    #         project_id,
    #         pc_id,
    #         self._namespace,
    #         self._bundle_cache_fallback_paths,
    #         use_global_bundle_cache,
    #         win_path,
    #         linux_path,
    #         mac_path
    #     )
    #
    #     # and install or update the configuration with the new content
    #     config.install_managed_configuration(
    #         descriptor_to_install,
    #         win_python,
    #         mac_python,
    #         linux_python
    #     )
    #
    #     # we can now boot up this config.
    #     self._report_progress("Starting up Toolkit...")
    #     tk = config.get_tk_instance(self._sg_user)
    #
    #     # and cache
    #     self._cache_apps(tk)
    #
    #     return pc_id
    #


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

    def _ensure_pipeline_config_exists(self, project_id):
        """
        Helper method. Creates a pipeline configuration entity if
        one doesn't already exist.

        :param project_id: Project id to check
        :returns: pipeline configuration id
        """
        # @todo - in the future, need to add namespace handling here.
        # if we are looking at a non-default config,
        # attempt to determine current user so that we can
        # populate the user restrictions field later on
        current_user = None
        if not self._is_primary_config() and self._sg_user.login:
            # the current user object is linked to a person
            current_user = self._sg_connection.find_one(
                "HumanUser",
                [["login", "is", self._sg_user.login]]
            )
            log.debug("Resolved current shotgun user %s to %s" % (self._sg_user, current_user))

        log.debug(
            "Looking for a pipeline configuration "
            "named '%s' for project %s" % (self._pipeline_configuration_name, project_id)
        )
        pc_data = self._sg_connection.find_one(
            constants.PIPELINE_CONFIGURATION_ENTITY_TYPE,
            [["code", "is", self._pipeline_configuration_name],
             ["project", "is", {"type": "Project", "id": project_id}]],
            ["users"]
        )
        log.debug("Shotgun returned %s" % pc_data)

        if pc_data is None:
            # pipeline configuration missing. Create a new one
            users = [current_user] if current_user else []
            pc_data = self._sg_connection.create(
                constants.PIPELINE_CONFIGURATION_ENTITY_TYPE,
                {"code": self._pipeline_configuration_name,
                 "project": {"type": "Project", "id": project_id},
                 "users": users
                 }
            )
            log.debug("Created new pipeline config: %s" % pc_data)

        elif current_user and current_user["id"] not in [x["id"] for x in pc_data["users"]]:
            log.debug("Adding %s to user access list..." % current_user)
            self._sg_connection.update(
                constants.PIPELINE_CONFIGURATION_ENTITY_TYPE,
                pc_data["id"],
                {"users": pc_data["users"] + [current_user]}
            )

        return pc_data["id"]

    def _is_primary_config(self):
        """
        Returns true if the pipeline configuration associated with the manager is
        the primary (default) one.
        """
        return self._pipeline_configuration_name == constants.PRIMARY_PIPELINE_CONFIG_NAME

    def _get_base_descriptor(self):
        """
        Resolves and returns a descriptor to the base config

        :return: ConfigDescriptor object
        """
        cfg_descriptor = create_descriptor(
            self._sg_connection,
            Descriptor.CONFIG,
            self._base_config_location,
            fallback_roots=self._bundle_cache_fallback_paths
        )
        log.debug("Base config resolved to: %r" % cfg_descriptor)
        return cfg_descriptor

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
                log.info("Item %s is already locally installed." % descriptor)

        # pass 3 - do post install
        if do_post_install:
            for descriptor in descriptors:
                self._report_progress("Running post install for %s" % descriptor)
                descriptor.ensure_shotgun_fields_exist(tk)
                descriptor.run_post_install(tk)

