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
from .paths import get_bundle_cache_root
from .configuration import Configuration, create_managed_configuration
from .resolver import BasicConfigurationResolver

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

        # public properties that can be changed
        self.bundle_cache_root = get_bundle_cache_root()
        self.pipeline_configuration_name = constants.PRIMARY_PIPELINE_CONFIG_NAME
        self.base_config_location = None

        self.cache_apps = True
        self.progress_callback = None

    def __repr__(self):
        repr  = "<TkManager "
        repr += " User %s\n" % self._sg_user
        repr += " Cache root %s\n" % self.bundle_cache_root
        repr += " Config %s\n" % self.pipeline_configuration_name
        repr += " Base %s >" % self.base_config_location
        return repr

    def validate(self, project_id):
        """
        Validate that the given project can receive mgmt operations.

        :return:
        """

    def upload_configuration(self, project_id):
        """
        Create a pipeline configuration uploaded to Shotgun

        :param project_id:
        :return:
        """
        log.debug("Begin uploading config to sgtk.")

        # first resolve the config we are going to upload
        cfg_descriptor = self._get_base_descriptor()
        log.debug("Will upload %s to %r, project %s" % (cfg_descriptor, self, project_id))

        # make sure it exists locally
        cfg_descriptor.ensure_local()

        # zip up the config
        config_root_path = cfg_descriptor.get_path()
        log.debug("Zipping up %s" % config_root_path)

        zip_tmp = os.path.join(
            tempfile.gettempdir(),
            "tk_%s" % uuid.uuid4().hex,
            datetime.datetime.now().strftime("%Y%m%d_%H%M%S.zip")
        )
        ensure_folder_exists(os.path.dirname(zip_tmp))
        zipfilehelper.zip_file(config_root_path, zip_tmp)

        # make sure a pipeline config record exists
        pc_id = self._ensure_pipeline_config_exists(project_id)

        log.debug("Uploading zip file...")
        attachment_id = self._sg_connection.upload(
            constants.PIPELINE_CONFIGURATION_ENTITY,
            pc_id,
            zip_tmp,
            constants.SHOTGUN_PIPELINECONFIG_ATTACHMENT_FIELD
        )
        log.debug("Upload complete!")

        # write uri
        uri = "sgtk:shotgun:%s:%s:%s:p%d:v%d" % (
            constants.PIPELINE_CONFIGURATION_ENTITY,
            constants.SHOTGUN_PIPELINECONFIG_ATTACHMENT_FIELD,
            self.pipeline_configuration_name,
            project_id,
            attachment_id
        )
        log.debug("Updating pipeline config with new uri %s" % uri)
        self._sg_connection.update(
            constants.PIPELINE_CONFIGURATION_ENTITY,
            pc_id,
            {constants.SHOTGUN_PIPELINECONFIG_URI_FIELD: uri}
        )

        return pc_id

    def create_disk_configuration(
        self,
        project_id,
        win_path=None,
        mac_path=None,
        linux_path=None,
        win_python=None,
        mac_python=None,
        linux_python=None
    ):
        """
        Creates a managed configuration on disk given the base location specified
        for the manager. The configuration will be downloaded and deployed for the
        given project. A pipeline configuration will be created with paths referencing
        the given locations on disk.

        A path to a python interpreter can be specified. If this is not set, the
        Shotgun desktop default python path will be used.

        This process is akin to the toolkit project setup tank command.

        :param project_id: Project id for which to create the configuration
        :param win_path: Optional windows install path
        :param mac_path: Otional mac install path
        :param linux_path: Optional linux install path.
        :param win_python: Optional python interpreter path.
        :param mac_python: Optional python interpreter path.
        :param linux_python: Optional python interpreter path.
        :return: Shotgun id for the pipeline relevant configuration
        """
        log.debug("Begin installing config on disk.")

        # check that we have a local path and interpreter
        curr_os_path = {"win32": win_path, "linux2": linux_path, "darwin": mac_path}[sys.platform]

        if curr_os_path is None:
            raise ShotgunDeployError("Need to specify a path for the current operating system!")

        # first resolve the config we are going to use to base the project on
        descriptor_to_install = self._get_base_descriptor()
        log.debug("Configuration will be based on: %r" % descriptor_to_install)

        # make sure a pipeline config record exists
        pc_id = self._ensure_pipeline_config_exists(project_id)

        # create an object to represent our configuration install
        config = create_managed_configuration(
            self._sg_connection,
            self.bundle_cache_root,
            project_id,
            pc_id,
            win_path,
            linux_path,
            mac_path
        )

        # first make sure a scaffold is in place
        config.ensure_project_scaffold()
        # if there is already content in there, back it up
        config.move_to_backup()
        # and install new content
        config.install_external_configuration(descriptor_to_install)
        # create a tank command
        config.create_tank_command(win_python, mac_python, linux_python)

        # update the paths record
        log.debug("Updating pipeline configuration %s with new paths..." % pc_id)
        self._sg_connection.update(
            constants.PIPELINE_CONFIGURATION_ENTITY,
            pc_id,
            {"linux_path": linux_path,
             "windows_path": win_path,
             "mac_path": mac_path}
        )

        # we can now boot up this config.
        tk = config.get_tk_instance(self._sg_user)

        # and cache
        if self.cache_apps:
            self._cache_apps(tk)

        return pc_id


    def bootstrap_sgtk(self, project_id=None):
        """
        Bootstrap into an sgtk instance

        :param project_id: Project to bootstrap into, None for site mode
        :returns: sgtk instance
        """
        log.debug("Begin bootstrapping sgtk.")

        resolver = BasicConfigurationResolver(
            self._sg_connection,
            self.bundle_cache_root,
            self.pipeline_configuration_name,
            self.base_config_location
        )

        config = resolver.resolve_project_configuration(project_id)

        # see what we have locally
        status = config.status()

        if status == Configuration.LOCAL_CFG_UP_TO_DATE:
            log.info("Your configuration is up to date.")

        elif status == Configuration.LOCAL_CFG_MISSING:
            log.info("A brand new configuration will be created locally.")
            config.ensure_project_scaffold()
            config.update_configuration()

        elif status == Configuration.LOCAL_CFG_OLD:
            log.info("Your local configuration is out of date and will be updated.")
            config.ensure_project_scaffold()
            config.move_to_backup()
            config.update_configuration()

        elif status == Configuration.LOCAL_CFG_INVALID:
            log.info("Your local configuration looks invalid and will be replaced.")
            config.ensure_project_scaffold()
            config.move_to_backup()
            config.update_configuration()

        else:
            raise ShotgunDeployError("Unknown configuration update status!")

        # @todo - add rollback logic from zip config branch

        # we can now boot up this config.
        tk = config.get_tk_instance(self._sg_user)

        if self.cache_apps and status != Configuration.LOCAL_CFG_UP_TO_DATE:
            self._cache_apps(tk)

        return tk

    def bootstrap_engine(self, engine_name, entity=None):
        """
        Convenience method that bootstraps into the given engine.

        :param entity: Shotgun entity to launch engine for
        :param engine_name: name of engine to launch (e.g. tk-nuke)
        :return: engine instance
        """
        log.debug("bootstrapping into an engine.")

        if entity:

            data = self._sg_connection.find_one(
                entity["type"],
                [["id", "is", entity["id"]]],
                ["project"]
            )

            if not data.get("project"):
                raise ShotgunDeployError("Cannot resolve project for %s" % entity)
            project_id = data["project"]["id"]

        else:
            project_id = None

        tk = self.bootstrap_sgtk(project_id)
        log.debug("Bootstrapped into tk instance %r" % tk)

        if entity is None:
            ctx = tk.context_empty()
        else:
            ctx = tk.context_from_entity_dictionary(entity)

        log.debug("Attempting to start engine %s for context %r" % (engine_name, ctx))
        # @todo - fix this import
        import tank
        engine = tank.platform.start_engine(engine_name, tk, ctx)

        log.debug("Launched engine %r" % engine)
        return engine

    def _ensure_pipeline_config_exists(self, project_id):
        """
        Helper method. Creates a pipeline configuration entity if
        one doesn't already exist. Checks that the currently

        :param project_id:
        :return:
        """
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
            "named '%s' for project %s" % (self.pipeline_configuration_name, project_id)
        )
        pc_data = self._sg_connection.find_one(
            constants.PIPELINE_CONFIGURATION_ENTITY,
            [["code", "is", self.pipeline_configuration_name],
             ["project", "is", {"type": "Project", "id": project_id}]],
            ["users"]
        )
        log.debug("Shotgun returned %s" % pc_data)

        if pc_data is None:
            # pipeline configuration missing. Create a new one
            users = [current_user] if current_user else []
            pc_data = self._sg_connection.create(
                constants.PIPELINE_CONFIGURATION_ENTITY,
                {"code": self.pipeline_configuration_name,
                 "project": {"type": "Project", "id": project_id},
                 "users": users
                 }
            )
            log.debug("Created new pipeline config: %s" % pc_data)

        elif current_user and current_user["id"] not in [x["id"] for x in pc_data["users"]]:
            log.debug("Adding %s to user access list..." % current_user)
            self._sg_connection.update(
                constants.PIPELINE_CONFIGURATION_ENTITY,
                pc_data["id"],
                {"users": pc_data["users"] + [current_user]}
            )

        return pc_data["id"]


    def _is_primary_config(self):
        """
        Returns true if the pipeline configuration associated with the manager is
        the primary (default) one.
        """
        return self.pipeline_configuration_name == constants.PRIMARY_PIPELINE_CONFIG_NAME

    def _get_base_descriptor(self):
        """
        Resolves and returns a descriptor to the base config

        :return:
        """
        cfg_descriptor = create_descriptor(
            self._sg_connection,
            Descriptor.CONFIG,
            self.base_config_location,
            self.bundle_cache_root
        )
        log.debug("Base config resolved to: %r" % cfg_descriptor)
        return cfg_descriptor

    def _cache_apps(self, tk, do_post_install=False):
        # each entry in the config template contains instructions about which version of the app
        # to use. First loop over all environments and gather all descriptors we should download,
        # then go ahead and download and post-install them

        pc = tk.pipeline_configuration

        log.info("Downloading and installing apps...")

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
                log.info("Downloading %s..." % descriptor)
                descriptor.download_local()

            else:
                log.info("Item %s is already locally installed." % descriptor)


        if do_post_install:
            for descriptor in descriptors:
                log.debug("Post install for %s" % descriptor)
                descriptor.ensure_shotgun_fields_exist(tk)
                descriptor.run_post_install(tk)





