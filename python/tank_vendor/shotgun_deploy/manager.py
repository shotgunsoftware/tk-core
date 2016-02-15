# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import re
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
from .configuration import Configuration, create_managed_configuration, create_unmanaged_configuration

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
        self._sg_connection.upload(
            constants.PIPELINE_CONFIGURATION_ENTITY,
            pc_id,
            zip_tmp,
            constants.SHOTGUN_PIPELINECONFIG_ATTACHMENT_FIELD
        )
        log.debug("Upload complete!")

        return pc_id

    def create_disk_configuration(self, project_id, win_path=None, mac_path=None, linux_path=None, win_python=None, mac_python=None, linux_python=None):
        """
        Create a pipeline configuration on disk

        :return:
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




    def bootstrap_sgtk(self, project_id=None, skip_shotgun_lookup=False):
        """
        Bootstrap into an sgtk instance

        :returns: sgtk instance
        """
        log.debug("Begin bootstrapping sgtk.")

        if skip_shotgun_lookup:
            log.debug("Completely skipping shotgun lookup for bootstrap.")
            # no configuration in Shotgun. Fall back on base
            config = self._create_base_configuration(project_id)

        else:
            # look up in shotgun
            config = self._get_configuration_from_shotgun(project_id)

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



    def bootstrap_engine(self, engine_name, project_id=None, entity=None, skip_shotgun_lookup=False):
        """
        Convenience method that bootstraps into the given engine.

        :param engine_name: name of engine to launch (e.g. tk-nuke)
        :return: engine instance
        """
        log.debug("bootstrapping into an engine.")

        tk = self.bootstrap_sgtk(project_id, skip_shotgun_lookup)
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
                log.info("Downloading %s to the local Toolkit install location..." % descriptor)
                descriptor.download_local()

            else:
                log.info("Item %s is already locally installed." % descriptor)


        if do_post_install:
            for descriptor in descriptors:
                log.debug("Post install for %s" % descriptor)
                descriptor.ensure_shotgun_fields_exist(tk)
                descriptor.run_post_install(tk)

    def _create_base_configuration(self, project_id):
        """
        Helper method that creates a config wrapper object

        :param project_id:
        :return:
        """
        cfg_descriptor = self._get_base_descriptor()
        log.debug("Creating a configuration wrapper based on %r." % cfg_descriptor)

        # create an object to represent our configuration install
        return create_unmanaged_configuration(
            self._sg_connection,
            self.bundle_cache_root,
            cfg_descriptor,
            project_id,
            pipeline_config_id=None
        )



    def _get_configuration_from_shotgun(self, project_id):
        """

        :param project_id:
        :return:
        """
        # now resolve pipeline config details
        project_entity = None if project_id is None else {"type": "Project", "id": project_id}

        # find a pipeline configuration in Shotgun.
        log.debug("Checking pipeline configuration in Shotgun...")
        pc_data = self._sg_connection.find_one(
            constants.PIPELINE_CONFIGURATION_ENTITY,
            [["code", "is", self.pipeline_configuration_name],
             ["project", "is", project_entity]],
            ["mac_path",
             "windows_path",
             "linux_path",
             constants.SHOTGUN_PIPELINECONFIG_ATTACHMENT_FIELD]
        )
        log.debug("Shotgun returned: %s" % pc_data)

        lookup_dict = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path"}

        if pc_data and pc_data.get(lookup_dict[sys.platform]):
            # we have paths specified for the local platform!
            return create_managed_configuration(
                self._sg_connection,
                self.bundle_cache_root,
                project_id,
                pc_data.get("id"),
                pc_data.get("windows_path"),
                pc_data.get("linux_path"),
                pc_data.get("mac_path"),
            )

        elif pc_data:
            # we have a pipeline config. see if there is a url pointing at a zip or git url
            log.debug("Attempting to resolve pipeline locaation from sg config attachment...")
            cfg_descriptor = self._extract_pipeline_attachment_config_location(
                project_id,
                self.pipeline_configuration_name,
                pc_data.get(constants.SHOTGUN_PIPELINECONFIG_ATTACHMENT_FIELD)
            )
            log.debug("Resolved pipeline configuration to %r" % cfg_descriptor)
            if cfg_descriptor:
                return create_unmanaged_configuration(
                    self._sg_connection,
                    self.bundle_cache_root,
                    cfg_descriptor,
                    project_id,
                    pc_data.get("id")
                )

        # fall back on base
        return self._create_base_configuration(project_id)




    def _extract_pipeline_attachment_config_location(self, project_id, pc_name, attachment_data):
        """
        Given attachment data from Shotgun, create a location dictionary

        :param attachment_data:
        :return:
        """

        # the attachment can have the following formats
        #
        # Web url:
        # {'name': 'v1.2.3',
        #  'url': 'https://github.com/shotgunsoftware/tk-config-default',
        #  'content_type': None,
        #  'type': 'Attachment',
        #  'id': 141,
        #  'link_type': 'web'}
        #
        # Uploaded file:
        # {'name': 'v1.2.3.zip',
        #  'url': 'https://sg-media-usor-01.s3.amazonaws.com/...',
        #  'content_type': 'application/zip',
        #  'type': 'Attachment',
        #  'id': 139,
        #  'link_type': 'upload'}
        #
        # Locally linked via file system:
        #
        # {'local_path_windows': 'D:\\toolkit\\manne-dev-2\\project\\zip_test\\v1.2.3.zip',
        #  'name': 'v1.2.3.zip',
        #  'local_path_linux': '/mnt/manne-dev-2/project/zip_test/v1.2.3.zip',
        #  'url': 'file:///mnt/manne-dev-2/project/zip_test/v1.2.3.zip',
        #  'local_storage': {'type': 'LocalStorage', 'id': 1, 'name': 'primary'},
        #  'local_path': '/mnt/manne-dev-2/project/zip_test/v1.2.3.zip',
        #  'content_type': 'application/zip',
        #  'local_path_mac': '/mnt/manne-dev-2/project/zip_test/v1.2.3.zip',
        #  'type': 'Attachment',
        #  'id': 142,
        #  'link_type': 'local'}

        config_location = None

        if attachment_data is None:
            return None

        if attachment_data["link_type"] == "web":
            # some web urls are supported, others are not. The following
            # ones are supported:
            # git://github.com/manneohrstrom/tk-hiero-publish.git
            # https://github.com/manneohrstrom/tk-hiero-publish.git

            # the version tag to pick up from the git repo is fetched from
            # the url display name.

            url = attachment_data["url"]
            if url.startswith("git://") or (url.startswith("https://") and url.endswith(".git")):
                # if the name of the tag begins with vX, assume this is a version number
                # if not, resolve latest
                link_name = attachment_data["name"]
                if re.match("^v[0-9\.]\.", link_name):
                    log.debug("Will use tag %s in git repo" % link_name)
                    config_location = {"type": "git", "path": url, "version": link_name}
                else:
                    # find latest
                    log.debug("Will search for latest in git repo")
                    config_location = {"type": "git", "path": url, "version": "latest"}
            else:
                log.debug("Url '%s' not supported by the bootstrap." % url)

        elif attachment_data["link_type"] == "upload":
            config_location = {
                "type": "shotgun_uploaded_configuration",
                "project_id": project_id,
                "name": pc_name,
                "attachment_id": attachment_data["id"]
            }

        elif attachment_data["link_type"] == "local":
            local_path = attachment_data["local_path"]
            if local_path is None:
                log.debug("Attachment doesn't have a valid local path.")
            else:
                config_location = {"type": "path", "path": local_path}

        # create a descriptor from the location
        cfg_descriptor = create_descriptor(
            self._sg_connection,
            Descriptor.CONFIG,
            config_location,
            self.bundle_cache_root
        )

        return cfg_descriptor

