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

from .setup_project_core import run_setup_project, TankConfigInstaller
from .setup_project_wrappers import CmdlineSetupInteraction, APISetupInteraction

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
        
        # set up an API interaction handler class and seed it with all our parameters
        interaction_handler = APISetupInteraction(log,
                                                  computed_params["config_uri"], 
                                                  computed_params["project_id"], 
                                                  computed_params["project_folder_name"], 
                                                  computed_params["config_path_mac"], 
                                                  computed_params["config_path_linux"], 
                                                  computed_params["config_path_win"])
        
        # finally execute the actual project setup
        return run_setup_project(log,
                                 interaction_handler, 
                                 computed_params["check_storage_path_exists"], 
                                 computed_params["force"])
        
                
    def run_interactive(self, log, args):
        """
        Tank command accessor (tank setup_project)
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
        
        
        interaction_handler = CmdlineSetupInteraction(log)
        run_setup_project(log, interaction_handler, check_storage_path_exists, force)
        
        

class SetupProjectFactoryAction(Action):
    """
    Special handling of Project setup.
    
    This is a more complex alternative to the simple setup_project command.
    
    This class exposes a setup_project_factory command to the API only (no tank command support)
    which returns a factory command object which can then in turn construct project setup wizard instances which 
    can be used to build interactive wizard-style project setup processes.
    
    it is used like this:
    
    >>> import tank
    # create our factory object
    >>> factory = tank.get_command("setup_project_factory")
    # the factory can spit out set up wizards
    >>> setup_wizard = c.execute()
    # now set up various parameters etc on the project wizard
    # this can be an interactive process which includes validation etc. 
    >>> wizard.set_parameters(....)
    # lastly, execute the actual setup.
    >>> wizard.execute()
    
    """    
    def __init__(self):
        Action.__init__(self, 
                        "setup_project_factory", 
                        Action.GLOBAL, 
                        ("Returns a factory object which can be used to construct setup wizards. These wizards "
                         "can then be used to run an interactive setup process."), 
                        "Configuration")
        
        # no tank command support for this one because it returns an object
        self.supports_tank_command = False
        
        # this method can be executed via the API
        self.supports_api = True
        
        self.parameters = {}
                
    def run_interactive(self, log, args):
        """
        Tank command accessor
        """
        raise TankError("This Action does not support command line access")
        
    def run_noninteractive(self, log, parameters):
        """
        API accessor
        """        
        return SetupProjectWizard(log)
                


class SetupProjectWizard(object):
    """
    A class which wraps around the project setup functionality in toolkit
    """
    
    def __init__(self, log):
        """
        Constructor
        """
        self._log = log
        self._project_id = None
        self._force_project_setup = None
        self._config_uri = None
        self._project_name = None
        
    def set_project(self, project_id, force=False):
        """
        Specify which project that should be set up.
        
        :param project_id: Shotgun id for the project that should be set up.
        :param force: Allow for the setting up of existing projects.
        """
        self._project_id = project_id
        self._force_project_setup = force
        
    def set_config_uri(self, config_uri):
        """
        Validate and set a configuration uri to use with this setup wizard. 
        
        In order to proceed with further functions, such as setting a project name,
        the config uri needs to be set.

        A configuration uri describes an item in the app store, in git or a file system path. 
        This will attempt to access the configuration specified in the uri
        and may involve downloading it to disk from github or the app store.
        Once downloaded, it will ensure that all the declared storages in the 
        configuration exist in the system.
        
        {"display_name": "Default Config",
         "valid": False,
         "description": "some description of the config",
         "message": "Storages not found on disk!",  
         "storages": { "primary": { "description": "Where project files are saved", 
                                    "exists": True,
                                    "valid" : False,
                                    "message": "cannot find the local path /foo/bar"}}
        
        :param config_uri: string describing a path on disk, a github uri or the name of an app store config.
        :returns: a dictionary representing the configuration, see above for details.
        """

    def get_default_project_disk_name(self):
        """
        Returns a default project name from toolkit.
        
        Before you call this method, a config and a project must have been set.
        
        This will execute hooks etc and given the selected project id will
        return a suggested project name.
        
        :returns: string with a suggested project name
        """
        
        
    def validate_project_disk_name(self, project_name):
        """
        Validate the project disk name.
        
        Before you call this method, a config and a project must have been set.
        
        Checks that the project name is valid and returns path previews for all storages.
        Returns a dictionary on the form:
        
        {"valid": False,
         "message": "Invalid characters in project name!",  
         "storages": { "primary": { "darwin": "/foo/bar/project_name", 
                                    "linux2": "/foo/bar/project_name",
                                    "win32" : "c:\foo\bar\project_name"},
                       "textures": { "darwin": "/textures/project_name", 
                                    "linux2": "/textures/project_name",
                                    "win32" : "c:\textures\project_name"}}
        
        The operating systems are enumerated using sys.platform jargon.
        
        :param project_name: string with a project name.
        :returns: Dictionary, see above.
        """
        
        
    def set_project_name(self, project_name):
        """
        Set the desired name of the project.
        
        :param project_name: string with a project name.
        """
    
    def set_configuration_location(self, mac_path, windows_path, linux_path):
        """
        Specifies where the pipeline configuration should be located.
        
        :param mac_path: path on mac
        :param windows_path: path on windows
        :param linux_path: path on linux
        """
    
    def execute(self):
        """
        Execute the actual setup process.
        """
        
        # set up an API interaction handler class and seed it with all our parameters
        interaction_handler = APISetupInteraction(self._log,
                                                  self._config_uri, 
                                                  computed_params["project_id"], 
                                                  computed_params["project_folder_name"], 
                                                  computed_params["config_path_mac"], 
                                                  computed_params["config_path_linux"], 
                                                  computed_params["config_path_win"])
        
        # finally execute the actual project setup
        return run_setup_project(self._log, interaction_handler, True, self._force_project_setup)
    


    
