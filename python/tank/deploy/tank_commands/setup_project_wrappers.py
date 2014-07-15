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

import re
import sys
import os

from ...util import shotgun
from ...platform import constants
from ...errors import TankError
from ... import hook

from tank_vendor import yaml


class CmdlineSetupInteraction(object):
    """
    Handles interaction between the project setup logic and the user when 
    running as a command line session. This code will prompt the user to 
    enter parameters etc.
    """
    
    def __init__(self, log):
        """
        Constructor
        """
        self._log = log
            
    def confirm_continue(self):
        """
        Called when the logic needs an interactive session to issue a "ok to contine" prompt
        """
        val = raw_input("Continue with project setup (Yes/No)? [Yes]: ")
        if val == "" or val.lower().startswith("y"):
            return True
        elif val.lower().startswith("n"):
            return False
        else:
            raise TankError("Please answer Yes, y, no, n or press ENTER!")
        
    def select_template_configuration(self, sg):
        """
        Ask the user which config to use. Returns a config string.
        """
        
        
        self._log.info("")
        self._log.info("")
        self._log.info("------------------------------------------------------------------")
        self._log.info("Which configuration would you like to associate with this project?")
        
        primary_pcs = sg.find(constants.PIPELINE_CONFIGURATION_ENTITY, 
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
                       "enter the path to this config and it will be used for the "
                       "new project.")
        self._log.info("")
        self._log.info("You can also enter an url pointing to a git repository. Toolkit will then "
                       "clone this repository and base the config on its content.")
        self._log.info("")
        
        
        config_name = raw_input("[%s]: " % constants.DEFAULT_CFG).strip()
        if config_name == "":
            config_name = constants.DEFAULT_CFG
        return config_name
        
    
    def select_project(self, sg, force):
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
         
        projs = sg.find("Project", filters, ["id", "name", "sg_description", "tank_name"])
    
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
        
    def get_project_folder_name(self, sg, project_name, project_id, resolved_storages):
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
                                                      sg=sg, 
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
            # note how we replace slashes in the name with backslashes on windows...
            proj_path = os.path.join(current_os_path, suggested_folder_name.replace("/", os.path.sep))
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


#######################################################################################################################

class APISetupInteraction(object):
    """
    Handles interaction between the project setup logic and the user when 
    running via the API. This class implements the same methods as the 
    CmdlineSetupInteraction class above but instead of prompting the user
    interactively, it just dishes out a bunch of pre-defined values
    in the various methods.
    """
    
    def __init__(self, log, configuration_uri, project_id, project_folder_name, mac_pc_location, linux_pc_location, win_pc_location):
        self._log = log
        self._configuration_uri = configuration_uri
        self._project_id = project_id
        self._project_folder_name = project_folder_name
        
        self._mac_pc_location = mac_pc_location
        self._linux_pc_location = linux_pc_location
        self._win_pc_location = win_pc_location
            
    def confirm_continue(self):
        """
        Called when the logic needs an interactive session to issue a "ok to contine" prompt
        """
        # When in API mode, we just continue without prompting
        return True
        
    def select_template_configuration(self, sg):
        """
        The setup logic requests which configuration to use. 
        Returns a config string.
        """
        return self._configuration_uri        
        
    
    def select_project(self, sg, force):
        """
        Returns the project id and name for a project for which setup should be done.
        """

        proj = sg.find_one("Project", [["id", "is", self._project_id]], ["name", "tank_name"])
    
        if proj is None:
            raise TankError("Could not find a project with id %s!" % self._project_id)

        # if force is false then tank_name must be empty
        if force == False and proj["tank_name"] is not None:
            raise TankError("You are trying to set up a project which has already been set up. If you want to do "
                            "this, make sure to set the force parameter.")

        return (self._project_id, proj["name"])
        
    def get_project_folder_name(self, sg, project_name, project_id, resolved_storages):
        """
        Given a project entity in Shotgun (name, id), decide where the project data
        root should be on disk. This will verify that the selected folder exists
        in each of the storages required by the configuration. 

        Returns the project disk name which is selected, this name may 
        include slashes if the selected location is multi-directory.
        """
        return self._project_folder_name    
    
    def get_disk_location(self, resolved_storages, project_disk_name, install_root):
        """
        The project setup process is requesting where on disk it should place the project config.
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
        return {"darwin": self._mac_pc_location, "linux2": self._linux_pc_location, "win32": self._win_pc_location}

    
