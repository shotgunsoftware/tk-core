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
from .action_base import Action
from ...errors import TankError

from .setup_project_core import run_setup_project
from .setup_project_wrappers import CmdlineSetupInteraction, APISetupInteraction


class SetupProjectAction(Action):
    """
    Action that sets up a new Toolkit Project.
    """    
    def __init__(self):
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
                                                                         "level use cases relating to UNC paths."),
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
        

        
    def run_noninteractive(self, log, parameters):
        """
        API accessor
        """
        
        # validate params and seed default values
        computed_params = self._validate_parameters(parameters)
        
        interaction_handler = APISetupInteraction(log,
                                                  computed_params["config_uri"], 
                                                  computed_params["project_id"], 
                                                  computed_params["project_folder_name"], 
                                                  computed_params["config_path_mac"], 
                                                  computed_params["config_path_linux"], 
                                                  computed_params["config_path_win"])
        
        return run_setup_project(log,
                                 interaction_handler, 
                                 computed_params["check_storage_path_exists"], 
                                 computed_params["force"])
        
                
    def run_interactive(self, log, args):
        
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
        
        
        interaction_handler = CmdlineSetupInteraction(log)
        run_setup_project(log, interaction_handler, check_storage_path_exists, force)
        
        

