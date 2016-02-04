# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import sys

from . import util
from . import Descriptor
from . import constants
from . import descriptor_factory
from .errors import ShotgunDeployError
from .installed_configuration import InstalledConfiguration
from .paths import get_bundle_cache_root

log = util.get_shotgun_deploy_logger()


class ToolkitBootstrap(object):
    """
    A class that defines toolkit bootstrap operations
    """

    def __init__(self, sg_user):
        """
        Constructor

        :param sg_user: Authenticated Shotgun User object
        """
        self._sg_user = sg_user

        # public properties that can be changed
        self.bundle_cache_root = get_bundle_cache_root()

        self.pipeline_configuration_name = constants.PRIMARY_PIPELINE_CONFIG_NAME

        self.skip_shotgun_lookup = False

        self.fallback_config_location = None

        self.use_latest_fallback_config = True

        # potential additional overrides:
        # UI overlays
        # logging ?
        # expert flags -
        # warm up caches
        # cache apps?


    def _cache_apps(self, tk):
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
        num_descriptors = len(descriptors)
        for idx, descriptor in enumerate(descriptors):

            if not descriptor.exists_local():
                log.info("Downloading %s to the local Toolkit install location..." % descriptor)
                descriptor.download_local()

            else:
                log.info("Item %s is already locally installed." % descriptor)

        # # create required shotgun fields
        # if run_post_install:
        #     progress_cb("Running post install processes...")
        #     for descriptor in descriptors:
        #         log.debug("Post install for %s" % descriptor)
        #         descriptor.ensure_shotgun_fields_exist()
        #         descriptor.run_post_install(tk)


    def _extract_pipeline_attachment_config_location(self, pc_name, attachment_data):
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

        if attachment_data["link_type"] == "web":
            # some web urls are supported, others are not. The following
            # ones are supported:
            # git://github.com/manneohrstrom/tk-hiero-publish.git
            # https://github.com/manneohrstrom/tk-hiero-publish.git

            # the version tag to pick up from the git repo is fetched from
            # the url display name.

            url = attachment_data["url"]
            if url.startswith("git://") or (url.startswith("https://") and url.endswith(".git")):
                config_location = {
                    "type": "git",
                    "path": url,
                    "version": attachment_data["name"]
                }
            else:
                log.debug("Url '%s' not supported by the bootstrap." % url)

        elif attachment_data["link_type"] == "upload":
            config_location = {
                "type": "pipeline_configuation",
                "name": pc_name,
                "attachment_id": attachment_data["id"]
            }

        elif attachment_data["link_type"] == "local":
            local_path = attachment_data["local_path"]
            if local_path is None:
                log.debug("Attachment doesn't have a valid local path.")
            else:
                config_location = {"type": "path", "path": local_path}

        return config_location


    def bootstrap_sgtk(self, project_id=None):
        """
        Bootstrap into an sgtk instance

        :returns: sgtk instance
        """
        log.debug("Begin bootstrapping sgtk.")

        sg = self._sg_user.create_sg_connection()

        # now resolve pipeline config details
        project_entity = None if project_id is None else {"type": "Project", "id": project_id}

        pipeline_configuration_id = None

        if self.skip_shotgun_lookup:
            log.debug("Completely skipping shotgun lookup for bootstrap.")
            config_location = self.fallback_config_location

        else:

            # find a pipeline configuration in Shotgun.
            log.debug("Checking pipeline configuration in Shotgun...")
            pc_data = sg.find_one(
                constants.PIPELINE_CONFIGURATION_ENTITY,
                [["code", "is", self.pipeline_configuration_name],
                 ["project", "is", project_entity]],
                ["mac_path",
                 "windows_path",
                 "linux_path",
                 constants.SHOTGUN_PIPELINECONFIG_ATTACHMENT_FIELD]
            )

            log.debug("Shotgun returned: %s" % pc_data)

            # populate some values for later use
            if pc_data:
                pipeline_configuration_id = pc_data["id"]

            # now analyze the configuratiojn data for this pc.
            #
            # first see if we have the path fields set.
            lookup_dict = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }

            if pc_data is None:
                # nothing in shotgun
                log.debug("No pipeline config found. Reverting to external settings.")
                config_location = self.fallback_config_location

            elif pc_data.get(lookup_dict[sys.platform]):
                # paths specified in Shotgun
                log.debug("Using path found in PipelineConfiguration.%s" % lookup_dict[sys.platform])
                pc_path = pc_data.get(lookup_dict[sys.platform])
                config_location = {"type": "path", "path": pc_path}

            elif pc_data.get(constants.SHOTGUN_PIPELINECONFIG_ATTACHMENT_FIELD):
                # config attachment present in shotgun
                config_location = self._extract_pipeline_attachment_config_location(
                    self.pipeline_configuration_name,
                    pc_data.get(constants.SHOTGUN_PIPELINECONFIG_ATTACHMENT_FIELD)
                )

                if config_location is None:
                    # could not extract a location from attachment field. This could be
                    # because the field is there but not valid or supported on our
                    # system. One example is a local file link which doesn't have a
                    # valid representation on the current os.
                    log.debug(
                        "Pipeline configuration cannot resolve to valid resource. "
                        "Reverting to external settings."
                    )
                    config_location = self.fallback_config_location

            else:
                log.debug("Pipeline configuration empty. Reverting to external settings.")
                config_location = self.fallback_config_location

        log.debug("Determined config locator: %s" % config_location)

        # resolve the config as a descriptor object
        if self.use_latest_fallback_config:
            cfg_descriptor = descriptor_factory.create_latest_descriptor(
                sg,
                Descriptor.CONFIG,
                config_location,
                self.bundle_cache_root
            )

        else:
            cfg_descriptor = descriptor_factory.create_descriptor(
                sg,
                Descriptor.CONFIG,
                config_location,
                self.bundle_cache_root
            )

        log.debug("Resolved config descriptor %r" % cfg_descriptor)

        # create an object to represent our configuration install
        config = InstalledConfiguration(
                sg,
                self.bundle_cache_root,
                cfg_descriptor,
                project_id,
                pipeline_configuration_id
        )

        # see what we have locally
        status = config.status()

        if status == InstalledConfiguration.LOCAL_CFG_UP_TO_DATE:
            log.info("Your configuration is up to date.")

        elif status == InstalledConfiguration.LOCAL_CFG_MISSING:
            log.info("A brand new configuration will be created locally.")
            config.set_up_project_scaffold()

        elif status == InstalledConfiguration.LOCAL_CFG_OLD:
            log.info("Your local configuration is out of date and will be updated.")
            config.move_to_backup()
            config.set_up_project_scaffold()

        elif status == InstalledConfiguration.LOCAL_CFG_INVALID:
            log.info("Your local configuration looks invalid and will be replaced.")
            config.move_to_backup()
            config.set_up_project_scaffold()

        else:
            raise ShotgunDeployError("Unknown configuration update status!")

        # @todo - add rollback logic from zip config branch

        # we can now boot up this config.
        tk = config.get_tk_instance(self._sg_user)

        self._cache_apps(tk)

        return tk



    def bootstrap_engine(self, engine_name, project_id=None, entity=None):
        """
        Bootstraps into the given engine

        :param engine_name: name of engine to launch (e.g. tk-nuke)
        :return: engine instance
        """
        log.debug("bootstrapping into an engine.")

        sg = self._sg_user.create_sg_connection()
        log.debug("using %r to connect to Shotgun" % sg)

        tk = self.bootstrap_sgtk(project_id)
        log.debug("Bootstrapped into tk instance %r" % tk)

        if entity is None:
            ctx = tk.context_empty()
        else:
            ctx = tk.context_from_entity_dictionary(entity)

        log.debug("Attempting to start engine %s for context %r" % (engine_name, ctx))
        import tank
        engine = tank.platform.start_engine(engine_name, tk, ctx)

        log.debug("Launched engine %r" % engine)
        return engine


