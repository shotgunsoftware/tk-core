# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Utils and logic for creating new tank projects
"""

SG_LOCAL_STORAGE_OS_MAP = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }

import re
import sys
import os
import shutil
import tempfile
import uuid
from ..errors import TankError
from ..util import shotgun
from .. import api
from ..platform import constants
from . import util as deploy_util
from . import env_admin
from .. import pipelineconfig
from .. import hook

from .zipfilehelper import unzip_file

from tank_vendor import yaml


########################################################################################
# User Interaction

class CmdlineSetupInteraction(object):
    
    def __init__(self, log, sg):
        self._log = log
        self._sg = sg
            
    def confirm_continue(self):
        """
        Yes no confirm to continue
        """
        val = raw_input("Continue with project setup (Yes/No)? [Yes]: ")
        if val == "" or val.lower().startswith("y"):
            return True
        elif val.lower().startswith("n"):
            return False
        else:
            raise TankError("Please answer Yes, y, no, n or press ENTER!")
        
    def select_template_configuration(self):
        """
        Ask the user which config to use. Returns a config string.
        """
        
        
        self._log.info("")
        self._log.info("")
        self._log.info("------------------------------------------------------------------")
        self._log.info("Which configuration would you like to associate with this project?")
        
        primary_pcs = self._sg.find(constants.PIPELINE_CONFIGURATION_ENTITY, 
                                    [["code", "is", constants.PRIMARY_PIPELINE_CONFIG_NAME]],
                                    ["code", "project", "mac_path", "windows_path", "linux_path"])        

        if len(primary_pcs) > 0:
            self._log.info("")
            self._log.info("You can use the configuration from an existing project as a "
                           "template for this new project. All settings, apps and folder "
                           "configuration settings will be copied over to your new project. "
                           "The following configurations were found: ")
            self._log.info("")
            for ppc in primary_pcs:
                pc_path = ppc.get(SG_LOCAL_STORAGE_OS_MAP[sys.platform])
                if pc_path is None or pc_path == "":
                    # this Toolkit config does not exist on a disk that is reachable from this os
                    self._log.info("   %s: No valid config found for this OS!" % ppc.get("project").get("name"))
                else:
                    config_path = os.path.join(pc_path, "config")
                    self._log.info("   %s: '%s'" % (ppc.get("project").get("name"), config_path))
    
            self._log.info("")
            self._log.info("If you want to use any of the configs listed about for your new project, "
                           "just type in its path when prompted below.")
    
        self._log.info("")
        self._log.info("You can use the Default Configuration for your new project.  "
                       "The default configuration is a good sample config, demonstrating "
                       "a typical basic setup of the Shotgun Pipeline Toolkit using the "
                       "latest apps and engines. This will be used by default if you just "
                       "hit enter below.")
        self._log.info("")
        self._log.info("If you have a configuration stored somewhere on disk, you can "
                       "just enter the path to this config it will be used for the "
                       "new project.")
        self._log.info("")
        
        config_name = raw_input("[%s]: " % constants.DEFAULT_CFG).strip()
        if config_name == "":
            config_name = constants.DEFAULT_CFG
        return config_name
        
    
    def select_project(self, force):
        """
        Returns the project id and name for a project for which setup should be done.
        Will request the user to input console input to select project.
        """

        filters = [["name", "is_not", "Template Project"], 
                   ["sg_status", "is_not", "Archive"],
                   ["sg_status", "is_not", "Lost"],
                   ["archived", "is_not", True]]
    
        if force == False:
            # not force mode. Only show non-set up projects
            filters.append(["tank_name", "is", None])
         
        projs = self._sg.find("Project", filters, ["id", "name", "sg_description", "tank_name"])
    
        if len(projs) == 0:
            raise TankError("Sorry, no projects found! All projects seem to have already been "
                            "set up with the Shotgun Pipeline Toolkit. If you are an expert "
                            "user and want to run the setup on a project which already has been "
                            "set up, run the setup_project command with a --force option.")
            
        if force:
            self._log.info("")
            self._log.info("")
            self._log.info("Below are all active projects, including ones that have been set up:")
            self._log.info("--------------------------------------------------------------------")
            self._log.info("")
            
        else:
            self._log.info("")
            self._log.info("")
            self._log.info("Below are all projects that have not yet been set up with Toolkit:")
            self._log.info("-------------------------------------------------------------------")
            self._log.info("")
        
        for x in projs:
            # helper that formats a single project
            desc = x.get("sg_description")
            if desc is None:
                desc = "[No description]"
            
            # chop a long description
            if len(desc) > 50:
                desc = "%s..." % desc[:50]
            
            self._log.info("[%2d] %s" % (x.get("id"), x.get("name")))
            if x.get("tank_name"):
                self._log.info("Note: This project has already been set up.")
            self._log.info("     %s" % desc)
            self._log.info("")
            
        self._log.info("")
        answer = raw_input("Please type in the id of the project to connect to or ENTER to exit: " )
        if answer == "":
            raise TankError("Aborted by user.")
        try:
            project_id = int(answer)
        except:
            raise TankError("Please enter a number!")
        
        if project_id not in [ x["id"] for x in projs]:
            raise TankError("Id %d was not found in the list of projects!" % project_id)
        
        # get the project name
        project_name = None
        for p in projs:
            if p.get("id") == project_id:
                project_name = p.get("name")
                break
                            
        return (project_id, project_name)
        
    def get_project_folder_name(self, project_name, project_id, resolved_storages):
        """
        Given a project entity in Shotgun (name, id), decide where the project data
        root should be on disk. This will verify that the selected folder exists
        in each of the storages required by the configuration. It will prompt the user
        and can create these root folders if required (with open permissions).

        Returns the project disk name which is selected, this name may 
        include slashes if the selected location is multi-directory.
        """
        
        # see if there is a hook to procedurally evaluate this
        # 
        project_name_hook = shotgun.get_project_name_studio_hook_location()
        if os.path.exists(project_name_hook):
            # custom hook is available!
            suggested_folder_name = hook.execute_hook(project_name_hook, 
                                                      parent=None, 
                                                      sg=self._sg, 
                                                      project_id=project_id)
        else:
            # construct a valid name - replace white space with underscore and lower case it.
            suggested_folder_name = re.sub("\W", "_", project_name).lower()

        
        self._log.info("")
        self._log.info("")
        self._log.info("")
        self._log.info("Now you need to tell Toolkit where you are storing the data for this project.")
        self._log.info("The selected Toolkit config utilizes the following Local Storages, as ")
        self._log.info("defined in the Shotgun Site Preferences:")
        self._log.info("")
        for s in resolved_storages:
            # [{'code': 'primary', 'mac_path': '/tank_demo/project_data', 
            #   'windows_path': None, 
            #   'type': 'LocalStorage', 
            #   'id': 1, 'linux_path': None}]
            current_os_path = s.get(SG_LOCAL_STORAGE_OS_MAP[sys.platform])
            storage_name = s.get("code").capitalize()
            self._log.info(" - %s: %s" % (storage_name, current_os_path))
        
        # first, display a preview
        self._log.info("")
        self._log.info("Each of the above locations need to have a data folder which is ")
        self._log.info("specific to this project. These folders all need to be named the same thing.")
        self._log.info("They also need to exist on disk.")
        self._log.info("For example, if you named the project '%s', " % suggested_folder_name)
        self._log.info("the following folders would need to exist on disk:")
        self._log.info("")
        for s in resolved_storages:
            current_os_path = s.get(SG_LOCAL_STORAGE_OS_MAP[sys.platform])
            proj_path = os.path.join(current_os_path, suggested_folder_name)
            storage_name = s.get("code").capitalize()
            self._log.info(" - %s: %s" % (storage_name, proj_path))
        
        self._log.info("")

        # now ask for a value and validate
        while True:
            self._log.info("")
            proj_name = raw_input("Please enter a folder name [%s]: " % suggested_folder_name).strip()
            if proj_name == "":
                proj_name = suggested_folder_name
            self._log.info("...that corresponds to the following data locations:")
            self._log.info("")
            storages_valid = True
            for s in resolved_storages:
                current_os_path = s.get(SG_LOCAL_STORAGE_OS_MAP[sys.platform])
                # note how we replace slashes in the name with backslashes on windows...
                proj_path = os.path.join(current_os_path, proj_name.replace("/", os.path.sep))
                storage_name = s.get("code").capitalize()
                if os.path.exists(proj_path):
                    self._log.info(" - %s: %s [OK]" % (storage_name, proj_path))
                else:
                    
                    # try to create the folders
                    try:
                        os.makedirs(proj_path, 0777)
                        self._log.info(" - %s: %s [Created]" % (storage_name, proj_path))
                        storages_valid = True
                    except Exception, e:
                        self._log.error(" - %s: %s [Not created]" % (storage_name, proj_path))
                        self._log.error("   Please create path manually.")
                        self._log.error("   Details: %s" % e)
                        storages_valid = False
            
            self._log.info("")
            
            if storages_valid:
                # looks like folders exist on disk
                
                val = raw_input("Paths look valid. Continue? (Yes/No)? [Yes]: ")
                if val == "" or val.lower().startswith("y"):
                    break
            else:
                self._log.info("Please make sure that folders exist on disk for your project name!")
        
        return proj_name


        
    
    
    def get_disk_location(self, resolved_storages, project_disk_name, install_root):
        """
        Ask the user where the pipeline configuration should be located on disk.
        Returns a dictionary with keys according to sys.platform: win32, darwin, linux2
        
        :param resolved_storages: All the storage roots (Local storage entities in shotgun)
                                  needed for this configuration. For example: 
                                  [{'code': 'primary', 
                                    'id': 1,
                                    'mac_path': '/tank_demo/project_data', 
                                    'windows_path': None, 
                                    'type': 'LocalStorage',  
                                    'linux_path': None}]

        :param project_name: The Project.name field in Shotgun for the selected project.
        :param project_id: The Project.id field in Shotgun for the selected project.
        :param install_root: location of the core code
        """
                            
        self._log.info("")
        self._log.info("")
        self._log.info("Now it is time to decide where the configuration for this project should go. ")
        self._log.info("As of Toolkit v0.13, you can specify any location you want on disk. ")
        self._log.info("Typically, this is in a software install area where you keep ")
        self._log.info("all your Toolkit code and configuration. We will suggest defaults ")
        self._log.info("based on your current install.")
        
        # figure out the config install location. There are three cases to deal with
        # - 0.13 style layout, where they all sit together in an install location
        # - 0.12 style layout, where there is a tank folder which is the studio location
        #   and each project has its own folder.
        # - something else!
        
        # find the primary storage path and see where it points to
        primary_local_path = ""
        primary_local_storage = None
        for s in resolved_storages:
            if s.get("code") == constants.PRIMARY_STORAGE_NAME:
                primary_local_path = s.get(SG_LOCAL_STORAGE_OS_MAP[sys.platform])
                primary_local_storage = s
                break
        
        # handle old setup - in the old setup, we would have the following structure: 
        # /studio              <--- primary storage
        # /studio/tank         <--- studio install
        # /studio/project      <--- project location
        # /studio/project/tank <--- install location
        #
        # typical new style setup (not showing data locations)
        # /software/studio <-- studio install
        # /software/projX  <-- project install
        
        location = {"darwin": None, "linux2": None, "win32": None}
        os_nice_name = {"darwin": "Macosx", "linux2": "Linux", "win32": "Windows"}
        
        if os.path.abspath(os.path.join(install_root, "..")).lower() == primary_local_path.lower():
            # ok the parent of the install root matches the primary storage - means OLD STYLE!
            
            self._log.info("")
            self._log.info("Note! Your setup looks like it was created with Toolkit v0.12! While ")
            self._log.info("it is now possible to put your configuration anywhere you like, we ")
            self._log.info("will suggest defaults compatible with your existing installation.")
            
            for curr_os in SG_LOCAL_STORAGE_OS_MAP:
                
                sg_storage_path_value = primary_local_storage.get( SG_LOCAL_STORAGE_OS_MAP[curr_os] )
            
                if sg_storage_path_value:
                    # chop off any end slashes
                    sg_storage_path_value.rstrip("/\\")
                    sg_storage_path_value += "/%s/tank" % project_disk_name
                    if curr_os == "win32":
                        # ensure back slashes all the way
                        sg_storage_path_value = sg_storage_path_value.replace("/", "\\")
                    else:
                        # ensure slashes all the way
                        sg_storage_path_value = sg_storage_path_value.replace("\\", "/")
                        
                    location[ curr_os ] = sg_storage_path_value        
            
        else:
            # assume new style setup - in this case we need to go figure out the different
            # OS paths to the install location. These are kept in a config file.
            
            # note! we must read this value from a file like this - cannot just determine it
            # based on the currently running code - because we need to know the path on all
            # three platforms.
            
            # now read in the install_location.yml file
            cfg_yml = os.path.join(install_root, "config", "core", "install_location.yml")
            fh = open(cfg_yml, "rt")
            try:
                data = yaml.load(fh)
            finally:
                fh.close()
            
            linux_install_root = data.get("Linux")
            windows_install_root = data.get("Windows")
            mac_install_root = data.get("Darwin")
            
            # typical new style setup (not showing data locations)
            # /software/studio <-- studio install
            # /software/projX  <-- project install
            
            if linux_install_root is not None and linux_install_root.startswith("/"):
                chunks = linux_install_root.split("/")
                # pop the studio bit
                chunks.pop()
                # append project name
                chunks.extend( project_disk_name.split("/") ) 
                location["linux2"] = "/".join(chunks)
            
            if mac_install_root is not None and mac_install_root.startswith("/"):
                chunks = mac_install_root.split("/")
                # pop the studio bit
                chunks.pop()
                # append project name
                chunks.extend( project_disk_name.split("/") )
                location["darwin"] = "/".join(chunks)
            
            if windows_install_root is not None and (windows_install_root.startswith("\\") or windows_install_root[1] == ":"):
                chunks = windows_install_root.split("\\")
                # pop the studio bit
                chunks.pop()
                # append project name
                chunks.extend( project_disk_name.split("/") )
                location["win32"] = "\\".join(chunks)
            
            
        self._log.info("")
        self._log.info("You can press ENTER to accept the default value or to skip.")
        
        for x in location:
            curr_val = location[x]

            if curr_val is None:
                val = raw_input("%s : " % os_nice_name[x])
                if val == "":
                    self._log.info("Skipping. This Pipeline configuration will not support %s." % os_nice_name[x])
                else:
                    location[x] = val.strip()
                    
            else:
                val = raw_input("%s [%s]: " % (os_nice_name[x], location[x]))
                if val != "":
                    location[x] = val.strip()

        return location

    
    
###############################################################################################
# config processing    

class TankConfigInstaller(object):
    """
    Functionality for handling installation and validation of tank configs
    """
    
    def __init__(self, config_name, sg, sg_app_store, script_user, log):
        self._sg = sg
        self._sg_app_store = sg_app_store
        self._script_user = script_user
        self._log = log
        # now extract the cfg and validate        
        self._cfg_folder = self._process_config(config_name)
        self._roots_data = self._read_roots_file()

        if constants.PRIMARY_STORAGE_NAME not in self._roots_data:
            # need a primary storage in every config
            raise TankError("Looks like your configuration does not have a primary storage. "
                            "This is required. Please contact support for more info.")

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
        
    def _process_config(self, cfg_string):
        """
        Looks at the starter config string and tries to convert it into a folder
        Returns a path to a config.
        """
        # three cases:
        # tk-config-xyz
        # /path/to/file.zip
        # /path/to/folder
        if os.path.sep in cfg_string:
            # probably a file path!
            if os.path.exists(cfg_string):
                # either a folder or zip file!
                if cfg_string.endswith(".zip"):
                    return self._process_config_zip(cfg_string)
                else:
                    return self._process_config_dir(cfg_string)
            else:
                raise TankError("File path %s does not exist on disk!" % cfg_string)    
        
        elif cfg_string.startswith("tk-"):
            # app store!
            return self._process_config_app_store(cfg_string)
        
        else:
            raise TankError("Don't know how to handle config '%s'" % cfg_string)
    
    
    def validate_roots(self, check_storage_path_exists):
        """
        Validate that the roots exist in shotgun. 
        Returns the root paths from shotgun for each storage.
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

    def get_path(self):
        """
        Returns a path to a location on disk where this config resides
        """
        return self._cfg_folder

    def check_manifest(self, sg_version_str):
        """
        Looks for an info.yml manifest in the config and validates it
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






########################################################################################
# helper methods

def _get_current_core_file_location():
    """
    Given the location of the code, find the configuration which holds
    the installation location on all platforms.    
    """
    
    core_api_root = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "..", "..", "..", ".."))
    core_cfg = os.path.join(core_api_root, "config", "core")
    
    if not os.path.exists(core_cfg):
        full_path_to_file = os.path.abspath(os.path.dirname(__file__))
        raise TankError("Cannot resolve the core configuration from the location of the Toolkit Code! "
                        "This can happen if you try to move or symlink the Toolkit API. The "
                        "Toolkit API is currently picked up from %s which is an "
                        "invalid location." % full_path_to_file)
    

    location_file = os.path.join(core_cfg, "install_location.yml")
    if not os.path.exists(location_file):
        raise TankError("Cannot find '%s' - please contact support!" % location_file)

    # load the config file
    try:
        open_file = open(location_file)
        try:
            location_data = yaml.load(open_file)
        finally:
            open_file.close()
    except Exception, error:
        raise TankError("Cannot load config file '%s'. Error: %s" % (location_file, error))
        
    return location_data
       

def _make_folder(log, folder, permissions, create_placeholder_file = False):
    log.debug("Creating folder %s.." % folder)
    os.mkdir(folder, permissions)
    if create_placeholder_file:
        ph_path = os.path.join(folder, "placeholder")
        fh = open(ph_path, "wt")
        fh.write("This placeholder file was automatically generated by Toolkit.\n")
        fh.close()
    

def _copy_folder(log, src, dst): 
    """
    Alternative implementation to shutil.copytree
    Copies recursively with very open permissions.
    Creates folders if they don't already exist.
    """
    
    if not os.path.exists(dst):
        log.debug("Creating folder %s..." % dst)
        os.mkdir(dst, 0775)

    names = os.listdir(src)     
    for name in names: 
        
        # get rid of system files
        if name in [".svn", ".git", ".gitignore", "__MACOSX"]: 
            continue
        
        srcname = os.path.join(src, name) 
        dstname = os.path.join(dst, name) 

        try: 
            if os.path.isdir(srcname): 
                _copy_folder(log, srcname, dstname)             
            else: 
                log.debug("Copying %s --> %s" % (srcname, dstname))
                shutil.copy(srcname, dstname) 
        
        except (IOError, os.error), why: 
            raise TankError("Can't copy %s to %s: %s" % (srcname, dstname, str(why))) 
    
def _install_environment(env_obj, log):
    """
    Make sure that all apps and engines exist in the local repo.
    """
    
    # populate a list of descriptors
    descriptors = []
    
    for engine in env_obj.get_engines():
        descriptors.append( env_obj.get_engine_descriptor(engine) )
        
        for app in env_obj.get_apps(engine):
            descriptors.append( env_obj.get_app_descriptor(engine, app) )
            
    for framework in env_obj.get_frameworks():
        descriptors.append( env_obj.get_framework_descriptor(framework) )
            
    # ensure all apps are local - if not then download them
    for descriptor in descriptors:
        if not descriptor.exists_local():
            log.info("Downloading %s to the local Toolkit install location..." % descriptor)            
            descriptor.download_local()
            
        else:
            log.info("Item %s is already locally installed." % descriptor)

    # create required shotgun fields
    for descriptor in descriptors:
        descriptor.ensure_shotgun_fields_exist()
    
def _get_published_file_entity_type(log, sg):
    """
    Find the published file entity type to use for this project.
    
    Returns 'PublishedFile' if the PublishedFile entity type has
    been enabled, otherwise returns 'TankPublishedFile'
    """
    log.debug("Retrieving schema from Shotgun to determine entity type " 
              "to use for published files")
    
    pf_entity_type = "TankPublishedFile"
    try:
        sg_schema = sg.schema_read()
        if ("PublishedFile" in sg_schema
            and "PublishedFileType" in sg_schema
            and "PublishedFileDependency" in sg_schema):
            pf_entity_type = "PublishedFile"
    except Exception, e:
        raise TankError("Could not retrieve the Shotgun schema: %s" % e)

    log.debug(" > Using %s entity type for published files" % pf_entity_type)

    return pf_entity_type
    



########################################################################################
# main methods and entry points

def interactive_setup(log, install_root, check_storage_path_exists, force):
    old_umask = os.umask(0)
    try:
        return _interactive_setup(log, install_root, check_storage_path_exists, force)
    finally:
        os.umask(old_umask)
    
def _interactive_setup(log, install_root, check_storage_path_exists, force):
    """
    interactive setup which will ask questions via the console.
    
    :param install_root: location of the core code
    :param check_storage_path_exists: whether or not to check that the storage root exists
                                      this can be useful sometimes when setting up windows
                                      UNC paths.
    :param force: allow to set up an already set up project 
    """
    log.info("")
    log.info("Welcome to the Shotgun Pipeline Toolkit Project Setup!")
    log.info("")
        
    # now connect to shotgun
    try:
        log.info("Connecting to Shotgun...")
        sg = shotgun.create_sg_connection()        
        sg_version = ".".join([ str(x) for x in sg.server_info["version"]])
        log.debug("Connected to target Shotgun server! (v%s)" % sg_version)
    except Exception, e:
        raise TankError("Could not connect to Shotgun server: %s" % e)
    
    try:
        log.info("Connecting to the App Store...")
        (sg_app_store, script_user) = shotgun.create_sg_app_store_connection()
        sg_version = ".".join([ str(x) for x in sg_app_store.server_info["version"]])
        log.debug("Connected to App Store! (v%s)" % sg_version)
    except Exception, e:
        raise TankError("Could not connect to App Store: %s" % e)
    
    
    ###############################################################################################
    # Stage 1 - information gathering
    
    cmdline_ui = CmdlineSetupInteraction(log, sg)
    
    # now ask which config to use. Download if necessary and examine
    config_name = cmdline_ui.select_template_configuration()

    # now try to load the config
    cfg_installer = TankConfigInstaller(config_name, sg, sg_app_store, script_user, log)
    
    # validate the config against the shotgun where we are installing it 
    cfg_installer.check_manifest(sg_version)
    
    # now look at the roots yml in the config
    resolved_storages = cfg_installer.validate_roots(check_storage_path_exists)

    # ask which project to operate on
    (project_id, project_name) = cmdline_ui.select_project(force)
    
    # ask the user to confirm the folder name
    project_disk_folder = cmdline_ui.get_project_folder_name(project_name, project_id, resolved_storages)
    
    # validate that this is not crazy
    # note that the value can contain slashes and span across multiple folders
    if re.match("^[/a-zA-Z0-9_-]+$", project_disk_folder) is None:
        # bad name
        raise TankError("Invalid project folder '%s'! Please use alphanumerics, "
                        "underscores and dashes." % project_disk_folder)
    
    # now ask the user where the config should go    
    locations_dict = cmdline_ui.get_disk_location(resolved_storages, project_disk_folder, install_root)
    current_os_pc_location = locations_dict[sys.platform]
    
    # determine the entity type to use for Published Files:
    pf_entity_type = _get_published_file_entity_type(log, sg)

    ##################################################################
    # validate the local storages
    #
    
    
    for s in resolved_storages:
        
        # note! at this point, the storage has been checked and exists on disk.        
        current_os_path = s.get( SG_LOCAL_STORAGE_OS_MAP[sys.platform] )
        project_path = os.path.join(current_os_path, project_disk_folder)
        
        # make sure that the storage location is not the same folder
        # as the pipeline config location. That will confuse tank.
        if current_os_pc_location == project_path:
            raise TankError("Your configuration location %s has been set to the same "
                            "as one of the storage locations. This is not supported!" % current_os_pc_location)
        
        if not os.path.exists(project_path):
            raise TankError("The Project path %s for storage %s does not exist on disk! "
                            "Please create it and try again!" % (project_path, s.get("code")))
    
        tank_folder = os.path.join(project_path, "tank")
        if os.path.exists(tank_folder):
            # tank folder exists - make sure it is writable
            if not os.access(tank_folder, os.W_OK|os.R_OK|os.X_OK):
                raise TankError("The permissions setting for '%s' is too strict. The current user "
                                "cannot create files or folders in this location." % tank_folder)
        else:
            # not tank folder has been created in this storage
            # make sure we can create it
            if not os.access(project_path, os.W_OK|os.R_OK|os.X_OK):
                raise TankError("The permissions setting for '%s' is too strict. The current user "
                                "cannot create a tank folder in this location." % project_path)
            

    
    
    ##################################################################
    # validate the install location
    #
    
    if os.path.exists(current_os_pc_location):
        # pc location already exists - make sure it doesn't already contain
        # an install
        if os.path.exists(os.path.join(current_os_pc_location, "install")) or \
           os.path.exists(os.path.join(current_os_pc_location, "config")):
            raise TankError("Looks like the location '%s' already contains a "
                            "configuration!" % current_os_pc_location)
        # also make sure it has right permissions
        if not os.access(current_os_pc_location, os.W_OK|os.R_OK|os.X_OK):
            raise TankError("The permissions setting for '%s' is too strict. The current user "
                            "cannot create files or folders in this location." % current_os_pc_location)
        
    else:
        # path does not exist! 
        # make sure parent exists and is writable
    
        # find an existing parent path
        parent_os_pc_location = None
        curr_path = current_os_pc_location
        while curr_path != os.path.dirname(curr_path):
            
            # get parent folder
            curr_path = os.path.dirname(curr_path)
            if os.path.exists(curr_path):
                parent_os_pc_location = curr_path 
                break
    
        if parent_os_pc_location is None:
            raise TankError("The folder '%s' does not exist! Please create "
                            "it before proceeding!" % current_os_pc_location)
                
        # and make sure we can create a folder in it
        if not os.access(parent_os_pc_location, os.W_OK|os.R_OK|os.X_OK):
            raise TankError("Cannot create a project configuration in location '%s'! "
                            "The permissions setting for the closest parent folder that "
                            "can be detected, '%s', is too strict. The current user "
                            "cannot create folders in this location. Please create the "
                            "project configuration folder by hand and then re-run the project "
                            "setup." % (current_os_pc_location, parent_os_pc_location))
    
    
    ###############################################################################################
    # Stage 2 - summary and confirmation
    
    log.info("")
    log.info("")
    log.info("Project Creation Summary:")
    log.info("-------------------------")
    log.info("")
    log.info("You are about to set up the Shotgun Pipeline Toolkit for Project %s - %s " % (project_id, project_name))
    log.info("The following items will be created:")
    log.info("")
    log.info("* A Shotgun Pipeline configuration will be created:" )
    log.info("  - on Macosx:  %s" % locations_dict["darwin"])
    log.info("  - on Linux:   %s" % locations_dict["linux2"])
    log.info("  - on Windows: %s" % locations_dict["win32"])
    log.info("")
    core_api_locations = _get_current_core_file_location()
    log.info("* The Pipeline configuration will use the following Core API:")
    log.info("  - on Macosx:  %s" % core_api_locations["Darwin"])
    log.info("  - on Linux:   %s" % core_api_locations["Linux"])
    log.info("  - on Windows: %s" % core_api_locations["Windows"])
    log.info("")

    for x in resolved_storages:

        log.info("* Toolkit will connect to the project folder in Storage '%s':" % x["code"] )
        
        if x["mac_path"] is None:
            log.info("  - on Macosx: No path defined")
        else:
            # not using path.join because it only works with current platform
            path_str = "%s/%s" % (x["mac_path"], project_disk_folder)
            log.info("  - on Macosx: %s" % path_str)
            
        if x["linux_path"] is None:
            log.info("  - on Linux:  No path defined")
        else:
            # not using path.join because it only works with current platform
            path_str = "%s/%s" % (x["linux_path"], project_disk_folder)
            log.info("  - on Linux:  %s" % path_str)

        if x["windows_path"] is None:
            log.info("  - on Windows: No path defined")
        else:
            # not using path.join because it only works with current platform
            path_str = "%s\\%s" % (x["windows_path"], project_disk_folder)
            log.info("  - on Windows: %s" % path_str)

    log.info("")
    log.info("")
    
    if not cmdline_ui.confirm_continue():
        raise TankError("Installation Aborted.")    
    
    ###############################################################################################
    # Stage 3 - execution
    
    log.info("")
    log.info("Starting project setup.")
    
    # if we have the force flag enabled, remove any pipeline configurations
    if force:
        pcs = sg.find("PipelineConfiguration", 
                      [["project", "is", {"id": project_id, "type": "Project"} ]],
                      ["code"])
        for x in pcs:
            log.warning("Force mode: Deleting old pipeline configuration %s..." % x["code"])
            sg.delete("PipelineConfiguration", x["id"])
            
    # first do disk structure setup, this is most likely to fail.
    current_os_pc_location = locations_dict[sys.platform]    
    log.info("Installing configuration into '%s'..." % current_os_pc_location )
    if not os.path.exists(current_os_pc_location):
        # note that we have already validated that creation is possible
        _make_folder(log, current_os_pc_location, 0775)
    
    # create pipeline config base folder structure            
    _make_folder(log, os.path.join(current_os_pc_location, "cache"), 0777)    
    _make_folder(log, os.path.join(current_os_pc_location, "config"), 0775)
    _make_folder(log, os.path.join(current_os_pc_location, "install"), 0775)
    _make_folder(log, os.path.join(current_os_pc_location, "install", "core"), 0777)
    _make_folder(log, os.path.join(current_os_pc_location, "install", "core", "python"), 0777)
    _make_folder(log, os.path.join(current_os_pc_location, "install", "core", "setup"), 0777)
    _make_folder(log, os.path.join(current_os_pc_location, "install", "core.backup"), 0777)
    _make_folder(log, os.path.join(current_os_pc_location, "install", "core.backup", "activation_13"), 0777, True)
    _make_folder(log, os.path.join(current_os_pc_location, "install", "engines"), 0777, True)
    _make_folder(log, os.path.join(current_os_pc_location, "install", "apps"), 0777, True)
    _make_folder(log, os.path.join(current_os_pc_location, "install", "frameworks"), 0777, True)
    
    # copy the configuration into place
    _copy_folder(log, cfg_installer.get_path(), os.path.join(current_os_pc_location, "config"))
    
    # copy the tank binaries to the top of the config
    log.debug("Copying Toolkit binaries...")
    core_api_root = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "..", ".."))
    root_binaries_folder = os.path.join(core_api_root, "setup", "root_binaries")
    for file_name in os.listdir(root_binaries_folder):
        src_file = os.path.join(root_binaries_folder, file_name)
        tgt_file = os.path.join(current_os_pc_location, file_name)
        shutil.copy(src_file, tgt_file)
        os.chmod(tgt_file, 0775)
    
    # copy the python stubs
    log.debug("Copying python stubs...")
    tank_proxy = os.path.join(core_api_root, "setup", "tank_api_proxy")
    _copy_folder(log, tank_proxy, os.path.join(current_os_pc_location, "install", "core", "python"))
        
    # specify the parent files in install/core/core_PLATFORM.cfg
    log.debug("Creating core redirection config files...")
    for (uname, path) in _get_current_core_file_location().items():
        core_path = os.path.join(current_os_pc_location, "install", "core", "core_%s.cfg" % uname)
        fh = open(core_path, "wt")
        if path is None:
            fh.write("undefined")
        else:
            fh.write(path)
        fh.close()
        
    # write a file location file for our new setup
    sg_code_location = os.path.join(current_os_pc_location, "config", "core", "install_location.yml")
    
    # if we are basing our setup on an existing project setup, make sure we can write to the file.
    if os.path.exists(sg_code_location):
        os.chmod(sg_code_location, 0666)

    fh = open(sg_code_location, "wt")
    fh.write("# Shotgun Pipeline Toolkit configuration file\n")
    fh.write("# This file was automatically created by setup_project\n")
    fh.write("# This file reflects the paths in the primary pipeline\n")
    fh.write("# configuration defined for this project.\n")
    fh.write("\n")
    fh.write("Windows: '%s'\n" % locations_dict["win32"])
    fh.write("Darwin: '%s'\n" % locations_dict["darwin"])    
    fh.write("Linux: '%s'\n" % locations_dict["linux2"])                    
    fh.write("\n")
    fh.write("# End of file.\n")
    fh.close()    
    os.chmod(sg_code_location, 0444)
    
        
    # update the roots file in the config to match our settings
    log.debug("Writing roots.yml...")
    roots_path = os.path.join(current_os_pc_location, "config", "core", "roots.yml")
    
    # resuffle list of associated local storages to be a dict keyed by storage name
    # and with keys mac_path/windows_path/linux_path
    roots_data = {}
    for s in resolved_storages:
        roots_data[ s["code"] ] = {"windows_path": s["windows_path"],
                                   "linux_path": s["linux_path"],
                                   "mac_path": s["mac_path"]}
    try:
        fh = open(roots_path, "wt")
        yaml.dump(roots_data, fh)
        fh.close()
    except Exception, exp:
        raise TankError("Could not write to roots file %s. "
                        "Error reported: %s" % (roots_path, exp))
    
    
    # now ensure there is a tank folder in every storage    
    for s in resolved_storages:
        log.info("Setting up %s storage..." % s["code"] )
        log.debug("Storage: %s" % str(s))
        
        current_os_path = s.get( SG_LOCAL_STORAGE_OS_MAP[sys.platform] )
        
        tank_path = os.path.join(current_os_path, project_disk_folder, "tank")
        if not os.path.exists(tank_path):
            _make_folder(log, tank_path, 0777)
        
        cache_path = os.path.join(tank_path, "cache")
        if not os.path.exists(cache_path):
            _make_folder(log, cache_path, 0777)

        config_path = os.path.join(tank_path, "config")
        if not os.path.exists(config_path):
            _make_folder(log, config_path, 0777)
        
        if s["code"] == constants.PRIMARY_STORAGE_NAME:
            # primary storage - make sure there is a path cache file
            # this is to secure the ownership of this file
            cache_file = os.path.join(cache_path, "path_cache.db")
            if not os.path.exists(cache_file):
                log.debug("Touching path cache %s" % cache_file)
                fh = open(cache_file, "wb")
                fh.close()
                os.chmod(cache_file, 0666)
                
        # create file for configuration backlinks
        log.debug("Setting up storage -> PC mapping...")
        project_root = os.path.join(current_os_path, project_disk_folder)
        scm = pipelineconfig.StorageConfigurationMapping(project_root)
        
        # make sure there is no existing backlinks associated with the config
        #
        # this can be the case if the config setup is using a pre-0.13 setup
        # where the project tank folder and the install folder is the same,
        # and the project was based on another project and thefore when the 
        # files were copied across, the back mappings file also got accidentally
        # copied.
        #
        # it can also happen when doing a force re-install of a project.
        scm.clear_mappings()
        
        # and add our configuration
        scm.add_pipeline_configuration(locations_dict["darwin"], 
                                       locations_dict["win32"], 
                                       locations_dict["linux2"])    
    
    # creating project.tank_name record
    log.debug("Shotgun: Setting Project.tank_name to %s" % project_disk_folder)
    sg.update("Project", project_id, {"tank_name": project_disk_folder})
    
    # create pipeline configuration record
    log.debug("Shotgun: Creating Pipeline Config record...")
    data = {"project": {"type": "Project", "id": project_id},
            "linux_path": locations_dict["linux2"],
            "windows_path": locations_dict["win32"],
            "mac_path": locations_dict["darwin"],
            "code": constants.PRIMARY_PIPELINE_CONFIG_NAME}
    pc_entity = sg.create(constants.PIPELINE_CONFIGURATION_ENTITY, data)
    log.debug("Created data: %s" % pc_entity)
    
    # write the record to disk
    pipe_config_sg_id_path = os.path.join(current_os_pc_location, "config", "core", "pipeline_configuration.yml")
    log.debug("Writing to pc cache file %s" % pipe_config_sg_id_path)
    
    data = {}
    data["project_name"] = project_disk_folder
    data["pc_id"] = pc_entity["id"]
    data["project_id"] = project_id
    data["pc_name"] = constants.PRIMARY_PIPELINE_CONFIG_NAME 
    data["published_file_entity_type"] = pf_entity_type
    
    try:
        fh = open(pipe_config_sg_id_path, "wt")
        yaml.dump(data, fh)
        fh.close()
    except Exception, exp:
        raise TankError("Could not write to pipeline configuration cache file %s. "
                        "Error reported: %s" % (pipe_config_sg_id_path, exp))
    
    # and write a custom event to the shotgun event log
    log.debug("Writing app store stats...")
    data = {}
    data["description"] = "%s: An Toolkit Project named %s was created" % (sg.base_url, project_disk_folder)
    data["event_type"] = "TankAppStore_Project_Created"
    data["user"] = script_user
    data["project"] = constants.TANK_APP_STORE_DUMMY_PROJECT
    data["attribute_name"] = project_disk_folder
    sg_app_store.create("EventLogEntry", data)
    
    
    ##########################################################################################
    # install apps
    
    # We now have a fully functional tank setup! Time to start it up...
    pc = pipelineconfig.from_path(current_os_pc_location)
    
    # each entry in the config template contains instructions about which version of the app
    # to use.
    
    for env_name in pc.get_environments():
        env_obj = pc.get_environment(env_name)
        log.info("Installing apps for environment %s..." % env_obj)
        _install_environment(env_obj, log)

    ##########################################################################################
    # post processing of the install
    
    # run after project create script if it exists
    after_script_path = os.path.join(current_os_pc_location, "config", "after_project_create.py")
    if os.path.exists(after_script_path):
        log.info("Found a post-install script %s" % after_script_path)
        log.info("Executing post-install commands...")
        sys.path.insert(0, os.path.dirname(after_script_path))
        try:
            import after_project_create
            after_project_create.create(sg=sg, project_id=project_id, log=log)
        except Exception, e:
            if ("API read() invalid/missing string entity" in e.__str__()
                and "\"type\"=>\"TankType\"" in e.__str__()):
                # Handle a specific case where an old version of the 
                # after_project_create script set up TankType entities which
                # are now disabled following the migration to the 
                # new PublishedFileType entity
                log.info("")
                log.warning("The post install script failed to complete.  This is most likely because it "
                            "is from an old configuration that is attempting to create 'TankType' entities "
                            "which are now disabled in Shotgun.")
            else:
                log.info("")
                log.error("The post install script failed to complete: %s" % e)
        else:
            log.info("Post install phase complete!")            
        finally:
            sys.path.pop(0)

    log.info("")
    log.info("Your Toolkit Project has been fully set up.")
    log.info("")

    # show the readme file if it exists
    readme_file = os.path.join(current_os_pc_location, "config", "README")
    if os.path.exists(readme_file):
        log.info("")
        log.info("README file for template:")
        fh = open(readme_file)
        for line in fh:
            print line.strip()
        fh.close()
    
    log.info("")
    log.info("We recommend that you now run 'tank updates' to get the latest")
    log.info("versions of all apps and engines for this project.")
    log.info("")
    log.info("For more Apps, Support, Documentation and the Toolkit Community, go to")
    log.info("https://toolkit.shotgunsoftware.com")
    log.info("")        

    
    
