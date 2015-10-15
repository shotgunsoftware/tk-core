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
import os
import re
from .action_base import Action
from . import core_localize
from ...errors import TankError
from ...util import shotgun
from ...platform import constants
from ... import pipelineconfig_utils

from tank_vendor import yaml

from .setup_project_core import run_project_setup
from .setup_project_params import ProjectSetupParameters

SG_LOCAL_STORAGE_OS_MAP = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }

class SetupProjectAction(Action):
    """
    Action that sets up a new Toolkit Project.
    
    This is the standard command that is exposed via the setup_project tank command
    and API equivalent.
    """    
    def __init__(self):
        """
        Constructor
        """
        Action.__init__(self, 
                        "setup_project", 
                        Action.GLOBAL, 
                        "Sets up a new project with the Shotgun Pipeline Toolkit.", 
                        "Configuration")
        
        # this method can be executed via the API
        self.supports_api = True
        
        self.parameters = {}
        
        self.parameters["check_storage_path_exists"] = { "description": ("Check that the path to the storage exists. "
                                                                         "this is enabled by default but can be turned "
                                                                         "off in order to deal with certain expert "
                                                                         "level use cases relating to UNC paths. for "
                                                                         "example, if your storage is set to be "
                                                                         "'\\\\PROJECTS', this location cannot be "
                                                                         "validated to exist and this option needs to "
                                                                         "be used."),
                                                         "default": True,
                                                         "type": "bool" }
        
        self.parameters["force"] = { "description": ("Enabling this flag allows you to run the set up project on "
                                                     "projects which have already been previously set up. "),
                                     "default": False,
                                     "type": "bool" }
        
        self.parameters["project_id"] = { "description": "Shotgun id for the project you want to set up.",
                                          "default": None,
                                          "type": "int" }
        
        self.parameters["project_folder_name"] = { "description": ("Name of the folder which you want to be the root "
                                                                   "point of the created project. If a project already "
                                                                   "exists, this parameter must reflect the name of the "
                                                                   "top level folder of the project."),
                                                   "default": None,
                                                   "type": "str" }

        self.parameters["config_uri"] = { "description": ("The configuration to use when setting up this project. "
                                                          "This can be a path on disk to a directory containing a "
                                                          "config, a path to a git bare repo (e.g. a git repo path "
                                                          "which ends with .git) or 'tk-config-default' "
                                                          "to fetch the default config from the toolkit app store."),
                                          "default": "tk-config-default",
                                          "type": "str" }

        # note how the current platform's default value is None in order to make that required
        self.parameters["config_path_mac"] = { "description": ("The path on disk where the configuration should be "
                                                               "installed on Macosx."),
                                               "default": ( None if sys.platform == "darwin" else "" ),
                                               "type": "str" }

        self.parameters["config_path_win"] = { "description": ("The path on disk where the configuration should be "
                                                               "installed on Windows."),
                                               "default": ( None if sys.platform == "win32" else "" ),
                                               "type": "str" }

        self.parameters["config_path_linux"] = { "description": ("The path on disk where the configuration should be "
                                                               "installed on Linux."),
                                               "default": ( None if sys.platform == "linux2" else "" ),
                                               "type": "str" }
        
        # Special setting used by the shotgun desktop app to handle the current form of distributed
        # configs
        self.parameters["auto_path"] = { "description": ("Expert setting. Setting this to true means that a blank "
                                                         "path entry is written to the shotgun site pipeline "
                                                         "configuration. This can be used in conjunction with "
                                                         "a localized core to create a site configuration which "
                                                         "can have different locations on different machines. It "
                                                         "is then up to the bootstrap logic of the code that "
                                                         "starts up toolkit to determine where to go look for the "
                                                         "configuration. When setting this to true, you typically "
                                                         "only need to specify the path to the current operating "
                                                         "system configuration."),
                                     "default": False,
                                     "type": "bool" }
        
        

        
    def run_noninteractive(self, log, parameters):
        """
        Tank command API accessor. 
        Called when someone runs a tank command through the core API.
        
        :param log: std python logger
        :param parameters: dictionary with tank command parameters
        """
        # validate params and seed default values
        computed_params = self._validate_parameters(parameters)
        
        # connect to shotgun
        (sg, sg_app_store, sg_app_store_script_user) = self._shotgun_connect(log)
                        
        # create a parameters class
        params = ProjectSetupParameters(log, sg, sg_app_store, sg_app_store_script_user)
        
        # tell it which core to pick up. For the tank command, we just base it off the 
        # currently running API
        curr_core_path = pipelineconfig_utils.get_path_to_current_core()
        core_roots = pipelineconfig_utils.resolve_all_os_paths_to_core(curr_core_path)
        params.set_associated_core_path(core_roots["linux2"], core_roots["win32"], core_roots["darwin"])
        
        # specify which config to use
        params.set_config_uri(computed_params["config_uri"], computed_params["check_storage_path_exists"])
        
        # set expert auto path setting
        params.set_auto_path_mode(computed_params["auto_path"])
        
        # set the project
        params.set_project_id(computed_params["project_id"], computed_params["force"])
        params.set_project_disk_name(computed_params["project_folder_name"])
        
        # set the config path
        params.set_configuration_location(computed_params["config_path_linux"], 
                                          computed_params["config_path_win"], 
                                          computed_params["config_path_mac"])        
        
        # run overall validation of the project setup
        params.pre_setup_validation()
        
        # and finally carry out the setup
        run_project_setup(log, sg, sg_app_store, sg_app_store_script_user, params)
        
        # check if we should run the localization afterwards
        # if we are running a localized pc, the root path of the core
        # api is the same as the root path for the associated pc
        if pipelineconfig_utils.is_localized(curr_core_path):
            log.info("Localizing Core...")
            core_localize.do_localize(log, 
                                      params.get_configuration_location(sys.platform), 
                                      suppress_prompts=True)
                        
                        
                        
    def run_interactive(self, log, args):
        """
        Tank command accessor
        
        :param log: std python logger
        :param args: command line args
        """
        
        if len(args) not in [0, 1]:
            raise TankError("Syntax: setup_project [--no-storage-check] [--force]")
        
        check_storage_path_exists = True
        force = False
        
        if len(args) == 1 and args[0] == "--no-storage-check":
            check_storage_path_exists = False
            log.info("no-storage-check mode: Will not verify that the storage exists. This "
                     "can be useful if the storage is pointing directly at a server via a "
                     "Windows UNC mapping.")
            
        if len(args) == 1 and args[0] == "--force":
            force = True
            log.info("force mode: Projects already set up with Toolkit can be set up again.")

        elif len(args) == 1 and args[0] not in ["--no-storage-check", "--force"]:
            raise TankError("Syntax: setup_project [--no-storage-check] [--force]")
            check_storage_path_exists = False
        
        
        # connect to shotgun
        (sg, sg_app_store, sg_app_store_script_user) = self._shotgun_connect(log)
        
        # create a parameters class
        params = ProjectSetupParameters(log, sg, sg_app_store, sg_app_store_script_user)
        
        # tell it which core to pick up. For the tank command, we just base it off the 
        # currently running API
        curr_core_path = pipelineconfig_utils.get_path_to_current_core()
        core_roots = pipelineconfig_utils.resolve_all_os_paths_to_core(curr_core_path)        
        params.set_associated_core_path(core_roots["linux2"], core_roots["win32"], core_roots["darwin"])
        
        # now ask which config to use. Download if necessary and examine
        config_uri = self._select_template_configuration(log, sg)
    
        # now try to load the config
        params.set_config_uri(config_uri, check_storage_path_exists)
        
        # ask which project to operate on
        project_id = self._select_project(log, sg, force)
        params.set_project_id(project_id, force)
    
        # ask the user to confirm the folder name
        self._get_project_folder_name(log, sg, params)    
    
        # now ask the user where the config should go
        self._get_disk_location(log, params)
        
        # run overall validation of the project setup
        params.pre_setup_validation()
        
        # print overview
        self._emit_project_setup_summary(log, params)
        
        # check if user wants to continue
        if not self._confirm_continue(log):
            raise TankError("Installation Aborted.")
        
        # and finally carry out the setup
        run_project_setup(log, sg, sg_app_store, sg_app_store_script_user, params)
        
        # check if we should run the localization afterwards
        # if we are running a localized pc, the root path of the core
        # api is the same as the root path for the associated pc
        if pipelineconfig_utils.is_localized(curr_core_path):
            log.info("Localizing Core...")
            core_localize.do_localize(log, 
                                      params.get_configuration_location(sys.platform), 
                                      suppress_prompts=True)
        
        # display readme etc.
        readme_content = params.get_configuration_readme()
        if len(readme_content) > 0:
            log.info("")
            log.info("README file for template:")
            for line in readme_content:
                print line
        
        log.info("")
        log.info("We recommend that you now run 'tank updates' to get the latest")
        log.info("versions of all apps and engines for this project.")
        log.info("")
        log.info("For more Apps, Support, Documentation and the Toolkit Community, go to")
        log.info("https://support.shotgunsoftware.com")
        log.info("")        
        
        
    def _shotgun_connect(self, log):
        """
        Connects to the App store and to the associated shotgun site.
        Logging in to the app store is optional and in the case this fails,
        the app store parameters will return None. 
        
        The method returns a tuple with three parameters:
        
        - sg is an API handle associated with the associated site
        - sg_app_store is an API handle associated with the app store.
          Can be None if connection fails.
        - sg_app_store_script_user is a sg dict (with name, id and type) 
          representing the script user used to connect to the app store.
          Can be None if connection fails.
        
        :returns: (sg, sg_app_store, sg_app_store_script_user) - see above.
        """
        
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
            log.warning("Could not establish a connection to the app store! You can "
                        "still create new projects, but you have to base them on "
                        "configurations that reside on your local disk.")
            log.debug("The following error was raised: %s" % e)
            sg_app_store = None
            script_user = None
        
        return (sg, sg_app_store, script_user)
        
        
    def _confirm_continue(self, log):
        """
        Called when the logic needs an interactive session to issue a "ok to continue" prompt
        
        :returns: true or false
        """
        evaluated_value = None
        while evaluated_value is None:
            val = raw_input("Continue with project setup (Yes/No)? [Yes]: ")
            if val == "" or val.lower().startswith("y"):
                evaluated_value = True
            elif val.lower().startswith("n"):
                evaluated_value = False
            else:
                log.error("Please answer Yes, y, no, n or press ENTER for yes!")
        
        return evaluated_value

    def _select_template_configuration(self, log, sg):
        """
        Ask the user which config to use. Returns a config uri string.
        
        :param log: python logger
        :param sg: Shotgun API instance
        
        :returns: config uri string
        """
        log.info("")
        log.info("")
        log.info("------------------------------------------------------------------")
        log.info("Which configuration would you like to associate with this project?")
        
        primary_pcs = sg.find(constants.PIPELINE_CONFIGURATION_ENTITY, 
                                    [["code", "is", constants.PRIMARY_PIPELINE_CONFIG_NAME]],
                                    ["code", "project", "mac_path", "windows_path", "linux_path"])        

        if len(primary_pcs) > 0:
            log.info("")
            log.info("You can use the configuration from an existing project as a "
                     "template for this new project. All settings, apps and folder "
                     "configuration settings will be copied over to your new project. "
                     "The following configurations were found: ")
            log.info("")
            for ppc in primary_pcs:
                # As of 6.0.2, pipeline configurations can be project less, so skip those
                if ppc.get("project") is None:
                    continue

                pc_path = ppc.get(SG_LOCAL_STORAGE_OS_MAP[sys.platform])
                if pc_path is None or pc_path == "":
                    # this Toolkit config does not exist on a disk that is reachable from this os
                    log.info("   %s: No valid config found for this OS!" % ppc.get("project").get("name"))
                else:
                    config_path = os.path.join(pc_path, "config")
                    log.info("   %s: '%s'" % (ppc.get("project").get("name"), config_path))
    
            log.info("")
            log.info("If you want to use any of the configs listed about for your new project, "
                     "just type in its path when prompted below.")
    
        log.info("")
        log.info("You can use the Default Configuration for your new project.  "
                 "The default configuration is a good sample config, demonstrating "
                 "a typical basic setup of the Shotgun Pipeline Toolkit using the "
                 "latest apps and engines. This will be used by default if you just "
                 "hit enter below.")
        log.info("")
        log.info("If you have a configuration stored somewhere on disk, you can "
                 "enter the path to this config and it will be used for the "
                 "new project.")
        log.info("")
        log.info("You can also enter an url pointing to a git repository. Toolkit will then "
                 "clone this repository and base the config on its content.")
        log.info("")
        
        
        config_name = raw_input("[%s]: " % constants.DEFAULT_CFG).strip()
        if config_name == "":
            config_name = constants.DEFAULT_CFG
        return config_name
        
    
    def _select_project(self, log, sg, show_initialized_projects):
        """
        Returns the project id and name for a project for which setup should be done.
        Will request the user to input console input to select project.
        
        :param log: python logger
        :param sg: Shotgun API instance
        :param show_initialized_projects: Should alrady initialized projects be displayed in the listing?
        
        :returns: project_id
        """

        filters = [["name", "is_not", "Template Project"], 
                   ["sg_status", "is_not", "Archive"],
                   ["sg_status", "is_not", "Lost"],
                   ["archived", "is_not", True]]
    
        if show_initialized_projects == False:
            # not force mode. Only show non-set up projects
            filters.append(["tank_name", "is", None])
         
        projs = sg.find("Project", filters, ["id", "name", "sg_description", "tank_name"])
    
        if len(projs) == 0:
            raise TankError("Sorry, no projects found! All projects seem to have already been "
                            "set up with the Shotgun Pipeline Toolkit. If you are an expert "
                            "user and want to run the setup on a project which already has been "
                            "set up, run the setup_project command with a --force option.")
            
        if show_initialized_projects:
            log.info("")
            log.info("")
            log.info("Below are all active projects, including ones that have been set up:")
            log.info("--------------------------------------------------------------------")
            log.info("")
            
        else:
            log.info("")
            log.info("")
            log.info("Below are all projects that have not yet been set up with Toolkit:")
            log.info("-------------------------------------------------------------------")
            log.info("")
        
        for x in projs:
            # helper that formats a single project
            desc = x.get("sg_description")
            if desc is None:
                desc = "[No description]"
            
            # chop a long description
            if len(desc) > 50:
                desc = "%s..." % desc[:50]
            
            log.info("[%2d] %s" % (x.get("id"), x.get("name")))
            if x.get("tank_name"):
                log.info("Note: This project has already been set up.")
            log.info("     %s" % desc)
            log.info("")
            
        log.info("")
        answer = raw_input("Please type in the id of the project to connect to or ENTER to exit: " )
        if answer == "":
            raise TankError("Aborted by user.")
        try:
            project_id = int(answer)
        except:
            raise TankError("Please enter a number!")
        
        if project_id not in [ x["id"] for x in projs]:
            raise TankError("Id %d was not found in the list of projects!" % project_id)
        
        return project_id
        
    def _get_project_folder_name(self, log, sg, params):
        """
        Given a project entity in Shotgun (name, id), decide where the project data
        root should be on disk. This will verify that the selected folder exists
        in each of the storages required by the configuration. It will prompt the user
        and can create these root folders if required (with open permissions).

        :param log: python logger
        :param sg: Shotgun API instance
        :param params: ProjectSetupParameters instance which holds the project setup parameters.
        :returns: The project disk name which is selected, this name may 
                  include slashes if the selected location is multi-directory. 
        """
        
        suggested_folder_name = params.get_default_project_disk_name()
        
        log.info("")
        log.info("")
        log.info("")
        log.info("Now you need to tell Toolkit where you are storing the data for this project.")
        log.info("The selected Toolkit config utilizes the following Local Storages, as ")
        log.info("defined in the Shotgun Site Preferences:")
        log.info("")
        for storage_name in params.get_required_storages():
            current_os_path = params.get_storage_path(storage_name, sys.platform)
            log.info(" - %s: '%s'" % (storage_name, current_os_path))
        
        # first, display a preview
        log.info("")
        log.info("Each of the above locations need to have a data folder which is ")
        log.info("specific to this project. These folders all need to be named the same thing.")
        log.info("They also need to exist on disk.")
        log.info("For example, if you named the project '%s', " % suggested_folder_name)
        log.info("the following folders would need to exist on disk:")
        log.info("")
        for storage_name in params.get_required_storages():
            proj_path = params.preview_project_path(storage_name, suggested_folder_name, sys.platform)            
            log.info(" - %s: %s" % (storage_name, proj_path))
        
        log.info("")

        # now ask for a value and validate
        while True:
            log.info("")
            proj_name = raw_input("Please enter a folder name [%s]: " % suggested_folder_name).strip()
            if proj_name == "":
                proj_name = suggested_folder_name
            
            # validate the project name
            try:
                params.validate_project_disk_name(proj_name)
            except TankError, e:
                # bad project name!
                log.error("Invalid project name: %s" % e)
                # back to beginning
                continue
            
            log.info("...that corresponds to the following data locations:")
            log.info("")
            storages_valid = True
            for storage_name in params.get_required_storages():
                
                proj_path = params.preview_project_path(storage_name, proj_name, sys.platform)
                
                if os.path.exists(proj_path):
                    log.info(" - %s: %s [OK]" % (storage_name, proj_path))
                else:
                    
                    # try to create the folders
                    try:
                        
                        old_umask = os.umask(0)
                        try:
                            os.makedirs(proj_path, 0777)
                        finally:
                            os.umask(old_umask)                        
                        
                        log.info(" - %s: %s [Created]" % (storage_name, proj_path))
                        storages_valid = True
                    except Exception, e:
                        log.error(" - %s: %s [Not created]" % (storage_name, proj_path))
                        log.error("   Please create path manually.")
                        log.error("   Details: %s" % e)
                        storages_valid = False
            
            log.info("")
            
            if storages_valid:
                # looks like folders exist on disk
                
                val = raw_input("Paths look valid. Continue? (Yes/No)? [Yes]: ")
                if val == "" or val.lower().startswith("y"):
                    break
            else:
                log.info("Please make sure that folders exist on disk for your project name!")
        
        params.set_project_disk_name(proj_name)


    def _get_disk_location(self, log, params):
        """
        Ask the user where the pipeline configuration should be located on disk.       
        
        :param log: python logger
        :param params: ProjectSetupParameters instance which holds the project setup parameters.
        """
                            
        log.info("")
        log.info("")
        log.info("Now it is time to decide where the configuration for this project should go. ")
        log.info("Typically, this is in a software install area where you keep ")
        log.info("all your Toolkit code and configuration. We will suggest defaults ")
        log.info("based on your current install.")

        log.info("")
        log.info("You can press ENTER to accept the default value or to skip.")
        
        default_config_locations = self._get_default_configuration_location(log, params)
        
        linux_path = self._ask_location(log, default_config_locations["linux2"], "Linux")
        windows_path = self._ask_location(log, default_config_locations["win32"], "Windows")
        macosx_path = self._ask_location(log, default_config_locations["darwin"], "Macosx")

        params.set_configuration_location(linux_path, windows_path, macosx_path)

    def _get_default_configuration_location(self, log, params):
        """
        Returns default suggested location for configurations.
        Returns a dictionary with sys.platform style keys linux2/win32/darwin, e.g.
        
        { "darwin": "/foo/bar/project_name", 
          "linux2": "/foo/bar/project_name",
          "win32" : "c:\foo\bar\project_name"}        

        :param log: python logger
        :param params: project setup params object
        :returns: dictionary with paths
        """
        
        # figure out the config install location. There are three cases to deal with
        # - 0.13 style layout, where they all sit together in an install location
        # - 0.12 style layout, where there is a tank folder which is the studio location
        #   and each project has its own folder.
        # - installing off a localized core api, meaning that there is no obvious
        #   relationship between the config location and the core location
                
        location = {"darwin": None, "linux2": None, "win32": None}
        
        # get the path to the primary storage  
        primary_local_path = params.get_storage_path(constants.PRIMARY_STORAGE_NAME, sys.platform)        
        
        curr_core_path = pipelineconfig_utils.get_path_to_current_core()
        core_locations = pipelineconfig_utils.resolve_all_os_paths_to_core(curr_core_path)
        
        if pipelineconfig_utils.is_localized(curr_core_path):
            # the API we are using to run the setup from was localized. This means
            # that the API will not be shared between projects and with something
            # like the shotgun desktop workflow, the core API is installed in a 
            # system location like %APPDATA% or ~/Library.
            # So we cannot use that as a default. In this case, simply don't provide 
            # a default parameter.
            pass

        elif core_locations[sys.platform] is None:
            # edge case: the shared core location that we are trying to install from
            # is not set up to work with this operating system. In that case, skip
            # default generation 
            pass
        
        elif os.path.abspath(os.path.join(core_locations[sys.platform], "..")).lower() == primary_local_path.lower():
            # ok the parent of the install root matches the primary storage - means OLD STYLE (pre core 0.12)
            #
            # in this setup, we would have the following structure: 
            # /studio              <--- primary storage
            # /studio/tank         <--- core API install
            # /studio/project      <--- project data location
            # /studio/project/tank <--- toolkit configuation location

            if params.get_project_path(constants.PRIMARY_STORAGE_NAME, "darwin"):
                location["darwin"] = "%s/tank" % params.get_project_path(constants.PRIMARY_STORAGE_NAME, "darwin") 
                                                     
            if params.get_project_path(constants.PRIMARY_STORAGE_NAME, "linux2"):
                location["linux2"] = "%s/tank" % params.get_project_path(constants.PRIMARY_STORAGE_NAME, "linux2") 

            if params.get_project_path(constants.PRIMARY_STORAGE_NAME, "win32"):
                location["win32"] = "%s\\tank" % params.get_project_path(constants.PRIMARY_STORAGE_NAME, "win32") 

        else:
            # Core v0.12+ style setup - this is what is our default recommended setup
            # here, the project data is treated as a completely separate thing.
            #
            # typical new style setup (not showing project data locations)
            # /software/studio <-- core API install
            #
            # /software/proj_a  <-- project configuration
            # /software/proj_b  <-- project configuration
            # /software/proj_c  <-- project configuration
            #
            # In this case, we can determine the location of /software/studio by looking 
            # at the location of the running code.
            # we then suggest a configuration relative to this
            
            # get the project name on disk - note that this may contain slashes
            project_name_chunks = params.get_project_disk_name().split("/") # ['multi', 'tier', 'name']
            
            # note: linux_install_root.startswith("/") handles the case where the config file says "undefined"
            
            if core_locations["linux2"]:
                chunks = core_locations["linux2"].split("/") # e.g. /software/studio -> ['', 'software', 'studio']
                chunks.pop() # pop the studio bit (e.g ['', 'software'])
                chunks.extend(project_name_chunks) # append project name 
                location["linux2"] = "/".join(chunks)
            
            if core_locations["darwin"]:
                chunks = core_locations["darwin"].split("/") # e.g. /software/studio -> ['', 'software', 'studio']
                chunks.pop() # pop the studio bit (e.g ['', 'software'])
                chunks.extend(project_name_chunks) # append project name
                location["darwin"] = "/".join(chunks)
            
            if core_locations["win32"]:
                # split path into chunks
                # e.g. c:\software\studio -> ['c:', 'software', 'studio']
                # e.g. \\myserver\mymount\software\studio -> ['', '', 'myserver', 'mymount', 'software', 'studio']
                chunks = core_locations["win32"].split("\\") 
                chunks.pop() # pop the studio bit
                chunks.extend(project_name_chunks) # append project name
                location["win32"] = "\\".join(chunks)

        return location



    def _ask_location(self, log, default, os_nice_name):
        """
        Helper method - asks the user where to put a pipeline config.
        
        :param log: python logger
        :param default: default value
        :param os_nice_name: A display name for an operating system
        :returns: A path determined by the user
        """
        curr_val = default

        if curr_val is None:
            val = raw_input("%s : " % os_nice_name)
            if val == "":
                log.info("Skipping. This Pipeline configuration will not support %s." % os_nice_name)
            else:
                curr_val = val.strip()
                
        else:
            val = raw_input("%s [%s]: " % (os_nice_name, curr_val))
            if val != "":
                curr_val = val.strip()
        return curr_val

    def _emit_project_setup_summary(self, log, params):
        """
        Emit project summary to the given logger
        
        :param log: python logger object
        :param params: Parameters object which holds gathered project settings
        """    
        log.info("")
        log.info("")
        log.info("Project Creation Summary:")
        log.info("-------------------------")
        log.info("")
        log.info("You are about to set up the Shotgun Pipeline Toolkit "
                 "for Project %s - %s " % (params.get_project_id(), 
                                           params.get_project_disk_name()))
        log.info("The following items will be created:")
        log.info("")
        log.info("* A Shotgun Pipeline configuration will be created:" )
        log.info("  - on Macosx:  '%s'" % params.get_configuration_location("darwin"))
        log.info("  - on Linux:   '%s'" % params.get_configuration_location("linux2"))
        log.info("  - on Windows: '%s'" % params.get_configuration_location("win32"))
        log.info("")
        log.info("* The Pipeline configuration will use the following Core API:")
        log.info("  - on Macosx:  '%s'" % params.get_associated_core_path("darwin"))
        log.info("  - on Linux:   '%s'" % params.get_associated_core_path("linux2"))
        log.info("  - on Windows: '%s'" % params.get_associated_core_path("win32"))            
        log.info("")
        log.info("")


