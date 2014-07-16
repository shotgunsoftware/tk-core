# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

SG_LOCAL_STORAGE_OS_MAP = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }

import sys
import os
import tempfile
import uuid

from ...platform import constants
from ...errors import TankError
from ... import pipelineconfig

from ..zipfilehelper import unzip_file
from .. import util as deploy_util

from tank_vendor import yaml



class ProjectSetupParameters(object):
    """
    Class that holds all the various parameters needed to run a project setup
    """
    
    def __init__(self, config_template):
        """
        Constructor
        """
        
        self._config_template = config_template
    
    
    def get_project_id(self):
        """
        Returns the project id for the project to be set up
        """
        
    def get_project_name(self):
        """
        Returns the disk name to be given to the project.
        This may be a simple name "test_project" or 
        may contain slashes "test/project" for project names
        which span across multiple folder levels
        """
        
    def get_template_configuration(self):
        """
        Returns the template configuration to be installed for this project
        """
        
    def get_required_storages(self):
        """
        Returns a list of storage names which are required for this project
        """
        self._config_template.
        
        
    def get_project_path(self, storage_name, platform):
        """    
        Returns the project path given a platform and a storage
        Can be None
        """
        # not using path.join because it only works with current platform
        
    def get_config_disk_location(self, platform):
        """    
        Returns the path to the configuration for a given platform
        """
        
    def get_associated_core_path(self, platform):
        """
        Returns the location of the core API for a given platform.
        Can be None
        """




class TemplateConfiguration(object):
    """
    Functionality for handling installation and validation of tank configs.
    This class abstracts download and resolve of various config URLs, such 
    as 
    - app store based configs
    - git based configs
    - file system configs
    - configs copied across from other projects
    
    The constructor is initialized with a config_uri which can have the following syntax:
    
    - toolkit app store syntax:    tk-config-default
    - git syntax (ends with .git): git@github.com:shotgunsoftware/tk-config-default.git
                                   https://github.com/shotgunsoftware/tk-config-default.git
                                   /path/to/bare/repo.git
    - file system location:        /path/to/config
    
    For the app store, the config is downloaded and unpacked into the project location
    For the file system uri, the config folder is copied into the project location
    For git, the git repo is cloned into the config location, therefore being a live repository
    to which changes later on can be pushed or pulled.
    """
    
    def __init__(self, config_uri, sg, sg_app_store, script_user, log):
        """
        Constructor
        
        :param config_uri: location of config (see constructor docs for details)
        :param sg: Shotgun site API instance
        :param sg_app_store: Shotgun app store API instance
        :param script_user: The app store script entity used to connect. Dictionary with type and id.
        :param log: Log channel 
        """
        self._sg = sg
        self._sg_app_store = sg_app_store
        self._script_user = script_user
        self._log = log
        
        # now extract the cfg and validate        
        (self._cfg_folder, self._config_mode) = self._process_config(config_uri)
        self._config_uri = config_uri
        self._roots_data = self._read_roots_file()

        if constants.PRIMARY_STORAGE_NAME not in self._roots_data:
            # need a primary storage in every config
            raise TankError("Looks like your configuration does not have a primary storage. "
                            "This is required. Please contact support for more info.")

    
    ################################################################################################
    # Helper methods

    def _read_roots_file(self):
        """
        Read, validate and return the roots data from the config
        """
        # get the roots definition
        root_file_path = os.path.join(self._cfg_folder, "core", "roots.yml")
        if os.path.exists(root_file_path):
            root_file = open(root_file_path, "r")
            try:
                roots_data = yaml.load(root_file)
            finally:
                root_file.close()
            
            # validate it
            for x in roots_data:
                if "mac_path" not in roots_data[x]:
                    roots_data[x]["mac_path"] = None
                if "linux_path" not in roots_data[x]:
                    roots_data[x]["linux_path"] = None
                if "windows_path" not in roots_data[x]:
                    roots_data[x]["windows_path"] = None
            
        else: 
            # set up default roots data
            roots_data = { constants.PRIMARY_STORAGE_NAME: 
                            { "description": "A location where the primary data is located.",
                              "mac_path": "/studio/projects", 
                              "linux_path": "/studio/projects", 
                              "windows_path": "\\\\network\\projects"
                            },                          
                          }
            
        return roots_data
        
    
    def _process_config_zip(self, zip_path):
        """
        unpacks a zip config into a temp location
        """
        # unzip into temp location
        self._log.debug("Unzipping configuration and inspecting it...")
        zip_unpack_tmp = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
        unzip_file(zip_path, zip_unpack_tmp)
        template_items = os.listdir(zip_unpack_tmp)
        for item in ["core", "env", "hooks"]:
            if item not in template_items:
                raise TankError("Config zip '%s' is missing a %s folder!" % (zip_path, item))
        self._log.debug("Configuration looks valid!")
        
        return zip_unpack_tmp
    
    def _process_config_app_store(self, config_name):
        """
        Downloads a config zip from the app store and unzips it
        """
        
        if self._sg_app_store is None:
            raise TankError("Cannot download config - you are not connected to the app store!")
        
        # try download from app store...
        parent_entity = self._sg_app_store.find_one(constants.TANK_CONFIG_ENTITY, 
                                              [["sg_system_name", "is", config_name ]],
                                              ["code"]) 
        if parent_entity is None:
            raise Exception("Cannot find a config in the app store named %s!" % config_name)
        
        # get latest code
        latest_cfg = self._sg_app_store.find_one(constants.TANK_CONFIG_VERSION_ENTITY, 
                                           filters = [["sg_tank_config", "is", parent_entity],
                                                      ["sg_status_list", "is_not", "rev" ],
                                                      ["sg_status_list", "is_not", "bad" ]], 
                                           fields=["code", constants.TANK_CODE_PAYLOAD_FIELD],
                                           order=[{"field_name": "created_at", "direction": "desc"}])
        if latest_cfg is None:
            raise Exception("It looks like this configuration doesn't have any versions uploaded yet!")
        
        # now have to get the attachment id from the data we obtained. This is a bit hacky.
        # data example for the payload field, as returned by the query above:
        # {'url': 'http://tank.shotgunstudio.com/file_serve/attachment/21', 'name': 'tank_core.zip',
        #  'content_type': 'application/zip', 'link_type': 'upload'}
        #
        # grab the attachment id off the url field and pass that to the download_attachment()
        # method below.
        try:
            attachment_id = int(latest_cfg[constants.TANK_CODE_PAYLOAD_FIELD]["url"].split("/")[-1])
        except:
            raise TankError("Could not extract attachment id from data %s" % latest_cfg)
    
        self._log.info("Downloading Config %s %s from the App Store..." % (config_name, latest_cfg["code"]))
        
        zip_tmp = os.path.join(tempfile.gettempdir(), "%s_tank_cfg.zip" % uuid.uuid4().hex)
    
        bundle_content = self._sg_app_store.download_attachment(attachment_id)
        fh = open(zip_tmp, "wb")
        fh.write(bundle_content)
        fh.close()
    
        # and write a custom event to the shotgun event log to indicate that a download
        # has happened.
        data = {}
        data["description"] = "Config %s %s was downloaded" % (config_name, latest_cfg["code"])
        data["event_type"] = "TankAppStore_Config_Download"
        data["entity"] = latest_cfg
        data["user"] = self._script_user
        data["project"] = constants.TANK_APP_STORE_DUMMY_PROJECT
        data["attribute_name"] = constants.TANK_CODE_PAYLOAD_FIELD
        self._sg_app_store.create("EventLogEntry", data)
    
        # got a zip! Pass to zip extractor...
        return self._process_config_zip(zip_tmp)
    
    def _process_config_dir(self, dir_path):
        """
        Validates that the directory contains a tank config
        """
        template_items = os.listdir(dir_path)
        for item in ["core", "env", "hooks"]:
            if item not in template_items:
                raise TankError("Config location '%s' missing a %s folder!" % (dir_path, item))
        self._log.debug("Configuration looks valid!")
        return dir_path
        
        
    def _process_config_git(self, git_repo_str):
        """
        Validate that a git repo is correct, download it to a temp location
        """
        
        self._log.debug("Attempting to clone git uri '%s' into a temp location "
                        "for introspection..." % git_repo_str)
        
        clone_tmp = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
        self._log.info("Attempting to clone git repository '%s'..." % git_repo_str)
        self._clone_git_repo(git_repo_str, clone_tmp)
        
        return clone_tmp
        
        
    def _process_config(self, cfg_string):
        """
        Looks at the starter config string and tries to convert it into a folder
        Returns a path to a config.
        """
        # three cases:
        # tk-config-xyz
        # /path/to/file.zip
        # /path/to/folder
        if cfg_string.endswith(".git"):
            # this is a git repository!
            return (self._process_config_git(cfg_string), "git")
            
        elif os.path.sep in cfg_string:
            # probably a file path!
            if os.path.exists(cfg_string):
                # either a folder or zip file!
                if cfg_string.endswith(".zip"):
                    return (self._process_config_zip(cfg_string), "local")
                else:
                    return (self._process_config_dir(cfg_string), "local")
            else:
                raise TankError("File path %s does not exist on disk!" % cfg_string)    
        
        elif cfg_string.startswith("tk-"):
            # app store!
            return (self._process_config_app_store(cfg_string), "app_store")
        
        else:
            raise TankError("Don't know how to handle config '%s'" % cfg_string)
        
    def _clone_git_repo(self, repo_path, target_path):
        """
        Clone the specified git repo into the target path
        
        :param repo_path:   The git repo path to clone
        :param target_path: The target path to clone the repo to
        :raises:            TankError if the clone command fails
        """
        # Note: git doesn't like paths in single quotes when running on 
        # windows - it also prefers to use forward slashes!
        sanitized_repo_path = repo_path.replace(os.path.sep, "/")
        if os.system("git clone \"%s\" \"%s\"" % (sanitized_repo_path, target_path)) != 0:
            raise TankError("Could not clone git repository '%s'!" % repo_path)     
        
    
    ################################################################################################
    # Public interface
    
    def validate_roots(self, check_storage_path_exists):
        """
        Validate that the roots exist in shotgun. 
        Returns the root paths from shotgun for each storage.
        
        :param check_storage_path_exists: bool to indicate that a file system check should 
                                          be carried out to verify that the disk location exists.
        """
        #
        self._log.debug("Checking so that all the local storages are registered...")
        sg_storage = self._sg.find("LocalStorage", [],
                                    fields=["code", "linux_path", "mac_path", "windows_path"])

        storages = []

        # make sure that there is a storage in shotgun matching all storages for this config
        sg_storage_codes = [x.get("code") for x in sg_storage]
        cfg_storages = self._roots_data.keys()
        problems = False
        for s in cfg_storages:
            if s not in sg_storage_codes:
                # storage required by config is missing 
                problems = True
                self._log.error("")
                self._log.error("=== Missing Local File Storage in Shotgun! ===")
                self._log.error("The Toolkit configuration is referring to a storage location")
                self._log.error("named '%s'. However, no such storage has been defined " % s)
                self._log.error("in Shotgun. Each configuration defines one or more")
                self._log.error("data roots, to which files are written - all of these roots ")
                self._log.error("need to be defined in Shotgun as Local File Storages.")
                self._log.error("In order to fix this, go to your Shotgun, go into the ")
                self._log.error("site preferences and set up local file storage named ")
                self._log.error("'%s'. Note that you shouldn't include the project name" % s)
                self._log.error("when you set up this storage.")
            
            else:
                # find the sg storage paths and add to return data
                for x in sg_storage:
                    if x.get("code") == s:
                        storages.append(x)
                        local_storage_path = x.get( SG_LOCAL_STORAGE_OS_MAP[sys.platform] )
                        # make sure that the storage is configured!
                        if local_storage_path is None:
                            # storage def does not have the path for current os set
                            problems = True
                            self._log.error("")
                            self._log.error("=== Local file storage not configured ===")
                            self._log.error("The local file storage %s is needed by the Toolkit configuration " % s)
                            self._log.error("but it does not have a path configured for the current os platform! ")
                            self._log.error("Please go to the site preferences in shotgun and adjust.")

                        elif check_storage_path_exists and not os.path.exists(local_storage_path):
                            problems = True
                            self._log.error("")
                            self._log.error("=== File storage path does not exist! ===")
                            self._log.error("The local file storage %s is needed by the Toolkit configuration. " % s)
                            self._log.error("It points to the path '%s' on the current os, " % local_storage_path)
                            self._log.error("but that path does not exist on disk.")

        if problems:
            raise TankError("One or more issues with local storage setup detected. "
                            "Setup cannot continue! If you have any questions, you can "
                            "always drop us a line on toolkitsupport@shotgunsoftware.com")
        
        return storages

    def check_manifest(self):
        """
        Looks for an info.yml manifest in the config and validates it.
        Raises exceptions if there are compatibility problems.
        """
        
        self._log.info("")
                
        info_yml = os.path.join(self._cfg_folder, constants.BUNDLE_METADATA_FILE)
        if not os.path.exists(info_yml):
            self._log.warning("Could not find manifest file %s. Project setup will proceed without validation." % info_yml)
            return
    
        try:
            file_data = open(info_yml)
            try:
                metadata = yaml.load(file_data)
            finally:
                file_data.close()
        except Exception, exp:
            raise TankError("Cannot load configuration manifest '%s'. Error: %s" % (info_yml, exp))
    
        # display name
        if "display_name" in metadata:
            self._log.info("This is the '%s' config." % metadata["display_name"])
    
        # perform checks
        if "requires_shotgun_version" in metadata:
            # there is a sg min version required - make sure we have that!
            
            required_version = metadata["requires_shotgun_version"]
    
            # get the version for the current sg site as a string (1.2.3)
            sg_version_str = ".".join([ str(x) for x in self._sg.server_info["version"]])
    
            if deploy_util.is_version_newer(required_version, sg_version_str):
                raise TankError("This configuration requires Shotgun version %s "
                                "but you are running version %s" % (required_version, sg_version_str))
            else:
                self._log.debug("Config requires shotgun %s. You are running %s which is fine." % (required_version, sg_version_str))
                    
        if "requires_core_version" in metadata:
            # there is a core min version required - make sure we have that!
            
            required_version = metadata["requires_core_version"]
            
            # now figure out the current version of the core api
            curr_core_version = pipelineconfig.get_core_api_version_based_on_current_code()
    
            if deploy_util.is_version_newer(required_version, curr_core_version):        
                raise TankError("This configuration requires Toolkit Core version %s "
                                "but you are running version %s" % (required_version, curr_core_version))
            else:
                self._log.debug("Config requires Toolkit Core %s. You are running %s which is fine." % (required_version, curr_core_version))


    def create_configuration(self, target_path):
        """
        Creates the configuration folder in the target path
        """
        if self._config_mode == "git":
            # clone the config into place
            self._log.info("Cloning git configuration into '%s'..." % target_path)
            self._clone_git_repo(self._config_uri, target_path)
        else:
            # copy the config from its source location into place
            _copy_folder(self._log, self._cfg_folder, target_path )

    
    




