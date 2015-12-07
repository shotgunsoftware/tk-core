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
import tempfile
import uuid
from tank_vendor import yaml
from .action_base import Action
from ..zipfilehelper import unzip_file
from ...errors import TankError
from ...platform import constants
from .setup_project_core import synchronize_project

class SynchronizeConfigurationAction(Action):
    """
    Action that sets up a new Toolkit Project.
    
    This is the standard command that is exposed via the setup_project tank command
    and API equivalent.
    """
    CONFIG_INFO_FILE = "config_info.yml"
    SG_CONFIG_FIELD = "sg_config"
    
    (LOCAL_CFG_UP_TO_DATE, LOCAL_CFG_OLD, LOCAL_CFG_INVALID, LOCAL_CFG_MISSING) = range(4)
    
    def __init__(self):
        """
        Constructor
        """
        Action.__init__(self, 
                        "synchronize", 
                        Action.TK_INSTANCE, 
                        "Synchronizes a pipeline configuration.", 
                        "Configuration")
        
        # this method can be executed via the API
        self.supports_api = True

        self.parameters = {}
        
        self.parameters["pipeline_configuration"] = { "description": "Pipeline config id to sync",
                                                      "default": "Primary",
                                                      "type": "str" }
        
        self.parameters["project_id"] = { "description": "Shotgun id for the project you want to set up.",
                                          "default": None,
                                          "type": "int" }
        
        self.parameters["progress_callback"] = { "description": "Progress callback",
                                                "default": None,
                                                "type": "function" }

        
    def run_noninteractive(self, log, parameters):
        """
        Tank command API accessor. 
        Called when someone runs a tank command through the core API.
        
        :param log: std python logger
        :param parameters: dictionary with tank command parameters
        """
        # validate params and seed default values
        computed_params = self._validate_parameters(parameters)
        
        return self._synchronize(log, 
                                 parameters["project_id"], 
                                 parameters["pipeline_configuration"],
                                 computed_params["progress_callback"])
                        
    def run_interactive(self, log, args):
        """
        Tank command accessor
        
        :param log: std python logger
        :param args: command line args
        """
        if len(args) != 2:
            raise TankError("Syntax: synchronize project_id config")

        project_id = int(args[0])
        config_name = args[1]
        self._synchronize(log, project_id, config_name)
    
    def _synchronize(self, log, project_id, pipeline_config_name, progress_cb=None):
        """
        Do the actual synchronize.
        
        The callback function should have the following signature:
        
        def callback(chapter_str, percent_progress_int=None)
        
        The installer will run through several "chapters" throughout the install
        and each of these will have a separate progress calculation. Some chapters
        are fast and/or difficult to quantify into steps - in this case, the 
        percent_progress_int parameter will be passed None. For such chapters,
        the callback will be called only once.
        
        For chapters which report progress, the callback will be called multiple times,
        each time with an incremented progress. This is an int value in percent.
        
        :param log: python log object
        :param project_id: Project id to sync
        :param pipeline_config_name: Pipeline configuration name
        :param progress_cb: Progress callback. See above for details.        
        """
        log.debug("Running synchronize for project id %d and pipeline config '%s'" % (project_id, pipeline_config_name))
        
        pc = self.tk.shotgun.find_one("PipelineConfiguration", 
                                      [["code", "is", pipeline_config_name], 
                                       ["project", "is", {"type": "Project", "id": project_id}]],
                                      ["id", "windows_path", "mac_path", "linux_path", self.SG_CONFIG_FIELD])
        if pc is None:    
            raise TankError("Couldn't find a pipeline configuration named '%s' for the given project" % pipeline_config_name)
        
        log.debug("Resolved pipeline configuration: \n%s" % pc)

        if pc[self.SG_CONFIG_FIELD] is None:
            log.info("This pipeline configuration does not have cloud data.") 
            return

        # locate zip - there are three different forms
        #
        #
        # Web url:
        # {'name': 'config in github', 
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


        # @TODO - support other attachment types (github urls!) 
        if pc[self.SG_CONFIG_FIELD]["link_type"] != "upload":
            raise TankError("Cloud based configuration currently only supports "
                            "uploaded configurations.")
        
        # calculate where the config should go        
        config_root = self.tk.execute_core_hook_method(constants.CACHE_LOCATION_HOOK_NAME,
                                                       "managed_config",
                                                       project_id=project_id,
                                                       pipeline_configuration_id=pc["id"])
        
        log.debug("The local config is located here: '%s'" % config_root)
        
        # see what we have locally
        status = self._check_local_status(pc[self.SG_CONFIG_FIELD], config_root)
        
        if status == self.LOCAL_CFG_UP_TO_DATE:
            log.info("Your configuration is up to date.")
            return
        
        elif status == self.LOCAL_CFG_MISSING:
            log.info("A brand new configuration will be created locally.")
            
        elif status == self.LOCAL_CFG_OLD:
            log.info("Your local configuration is out of date and "
                     "will be updated.")

        elif status == self.LOCAL_CFG_INVALID:
            log.info("Your local configuration looks invalid and "
                     "will be replaced.")
        
        else:
            raise TankError("Unknown configuration update status!")
        
        # download config attachment from Shotgun
        #
        # @todo: maybe can use the config wrapper class used in proj setup
        # here to generically support any config 'uri'?
        #
        zip_path = os.path.join(tempfile.gettempdir(), "tk_cfg_%s.zip" % uuid.uuid4().hex)
        log.debug("downloading attachment to '%s'" % zip_path)
        bundle_content = self.tk.shotgun.download_attachment(pc[self.SG_CONFIG_FIELD]["id"])
        fh = open(zip_path, "wb")
        fh.write(bundle_content)
        fh.close()
        
        # unpack cfg to temp and do some sanity checking
        zip_unpack_tmp = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
        log.debug("Unzipping configuration and inspecting it to '%s'" % zip_unpack_tmp)
        unzip_file(zip_path, zip_unpack_tmp)
        template_items = os.listdir(zip_unpack_tmp)
        for item in ["core", "env", "hooks"]:
            if item not in template_items:
                raise TankError("Config zip '%s' is missing a %s folder!" % (zip_path, item))
        log.debug("Configuration looks valid!")


        if status != self.LOCAL_CFG_MISSING:
            # a config already exists. Move it into a backup location, so that
            # we can rollback to previous config in case something goes wrong.
            config_backup_path = self.tk.execute_core_hook_method(constants.CACHE_LOCATION_HOOK_NAME,
                                                                  "managed_config_backup",
                                                                  project_id=project_id,
                                                                  pipeline_configuration_id=pc["id"])
            # move it out of the way
            log.debug("Backing up config %s -> %s" % (config_root, config_backup_path))
            
            # the config_backup_path has already been created by the hook, so we 
            # are moving the config folder *into* the backup folder to make
            # the system as permissions friendly as possible and give maximum
            # flexibility to the hook logic to do whatever it needs to do.
            backup_target_path = os.path.join(config_backup_path, os.path.basename(config_root))
            os.rename(config_root, backup_target_path)
        
            # make sure the folder is there as it was just renamed 
            config_root = self.tk.execute_core_hook_method(constants.CACHE_LOCATION_HOOK_NAME,
                                                           "managed_config",
                                                           project_id=project_id,
                                                           pipeline_configuration_id=pc["id"])
        
        else:
            backup_target_path = None
        
        try:
            # now begin deployment
            log.debug("Will synchronize into '%s'" % config_root)
            
            if progress_cb is None:
                # push progress reporting through the logger
                def progress_fn(chapter, progress=None):
                    if progress:
                        log.info("%s: %s%%" % (chapter, progress))
                    else:
                        log.info("%s" % chapter)
                
                progress_cb = progress_fn
            
            # check core
            core_location_path = os.path.join(zip_unpack_tmp, "core", "core_api.yml") 
            if os.path.exists(core_location_path):
                # the core_api.yml contains info about the core config:
                #
                # location:
                #    name: tk-core
                #    type: app_store
                #    version: v0.16.34
                
                log.debug("Detected core location file '%s'" % core_location_path)
                
                # read the file first
                fh = open(core_location_path, "rt")
                try:
                    data = yaml.load(fh)
                    location_dict = data["location"]
                except Exception, e:
                    raise TankError("Cannot read invalid core "
                                    "location file '%s': %s" % (core_location_path, e))
                finally:
                    fh.close()

                descriptor = self.tk.pipeline_configuration.get_core_descriptor(location_dict)
                log.debug("This config requires core %s" % descriptor)
                
                # cache core locally if not already cached
                log.debug("Making sure core exists locally...")
                descriptor.download_local()
                path_to_core = descriptor.get_path()
            
            else:
                # use currently running core API version as the source
                # this core API will be copied across into the config
                cur_core_ver = self.tk.pipeline_configuration.get_associated_core_version()
                log.debug("No core location file detected. Will copy the "
                          "currently running core (%s) into the project." % cur_core_ver)
                path_to_core = self.tk.pipeline_configuration.get_install_location()
                
            log.debug("Begin project sync!")
            synchronize_project(log, 
                                progress_cb, 
                                self.tk.shotgun, 
                                zip_unpack_tmp, 
                                config_root, 
                                path_to_core)
    
            # write info
            log.debug("Writing attachment metadata file")
            self._write_config_info_file(pc[self.SG_CONFIG_FIELD], config_root)

        except Exception, e:
            log.error("An error occurred during upgrade: %s" % e)
            if backup_target_path:
                log.info("Your previous config will be rolled back")
                
                failed_config_path = self.tk.execute_core_hook_method(constants.CACHE_LOCATION_HOOK_NAME,
                                                                      "managed_config_backup",
                                                                      project_id=project_id,
                                                                      pipeline_configuration_id=pc["id"])
                
                log.debug("Backing up failed config %s -> %s" % (config_root, failed_config_path))
                failed_backup_target_path = os.path.join(config_backup_path, os.path.basename(config_root))
                os.rename(config_root, failed_backup_target_path)
                
                log.info("Restoring previous backup %s -> %s" % (config_backup_path, config_root))
                os.rename(backup_target_path, config_root)
        
    def _write_config_info_file(self, sg_data, config_root):
        """
        Writes a cache file with info about where the config came from.
        
        :param sg_data: Attachment data from Shotgun to describe the cfg payload
        :param config_root: Root install path for the config  
        """
        config_info_file = os.path.join(config_root, "cache", self.CONFIG_INFO_FILE)
        fh = open(config_info_file, "wt")

        fh.write("# This file contains metadata describing what exact version\n")
        fh.write("# Of the config that was downloaded from Shotgun\n")
        fh.write("\n")
        fh.write("# Below follows details for the sg attachment that is\n")
        fh.write("# reflected within this local configuration.\n")
        fh.write("\n")
        
        metadata = {}
        # bake in which version of the deploy logic was used to push this config
        metadata["deply_generation"] = constants.CLOUD_CONFIG_DEPLOY_LOGIC_GENERATION
        # and include details about where the config came from
        metadata["sg_config_attachment"] = sg_data
        
        # write yaml
        yaml.safe_dump(metadata, fh)
        fh.write("\n")
        fh.close()

    def _check_local_status(self, sg_data, config_root):
        """
        Check the status of the local config.
        
        :param sg_data: Field data from attachment field for pipeline config.
        :param config_root: Computed root where the config should reside locally.
        :returns: LOCAL_CFG_UP_TO_DATE, LOCAL_CFG_OLD, LOCAL_CFG_INVALID, LOCAL_CFG_MISSING
        """

        # There are three different forms
        #
        #
        # Web url:
        # {'name': 'config in github', 
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
        
        
        # first check if there is any config at all
        # probe for tank command
        if not os.path.exists(os.path.join(config_root, "tank")):
            return self.LOCAL_CFG_MISSING  

        # local config exists. See if it is up to date.
        # look at the attachment id to determine the generation of the config.
        config_info_file = os.path.join(config_root, "cache", self.CONFIG_INFO_FILE)
        
        if not os.path.exists(config_info_file):
            # not sure what version this is.
            return self.LOCAL_CFG_INVALID
        
        fh = open(config_info_file, "rt")
        try:
            
            data = yaml.load(fh)
            deploy_generation = data["deply_generation"]
            local_attachment_id = data["sg_config_attachment"]["id"]
        except Exception:
            # yaml info not valid.
            return self.LOCAL_CFG_INVALID
        finally:
            fh.close()
        
        if deploy_generation != constants.CLOUD_CONFIG_DEPLOY_LOGIC_GENERATION:
            # different format or logic of the deploy itself. 
            # trigger a redeploy
            return self.LOCAL_CFG_OLD
        
        if local_attachment_id < sg_data["id"]:
            return self.LOCAL_CFG_OLD
        
        else:
            return self.LOCAL_CFG_UP_TO_DATE
 
