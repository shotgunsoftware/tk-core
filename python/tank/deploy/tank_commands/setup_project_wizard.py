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
from ...util import shotgun
from ...errors import TankError

from .setup_project_core import run_project_setup
from .setup_project_params import ProjectSetupParameters

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
        # connect to shotgun
        (sg, sg_app_store, sg_app_store_script_user) = self._shotgun_connect(log)
        # return a wizard object
        return SetupProjectWizard(log, sg, sg_app_store, sg_app_store_script_user)
                    
    def _shotgun_connect(self, log):
        """
        Connects to the App store and to the associated shotgun site.
        Logging in to the app store is optional and in the case this fails,
        the app store parameters will return None. 
        
        The method returns a tuple with three parameters:
        
        - sg is an API handle associated with the associated site
        - sg_app_store is an API handle associated with the app store
        - sg_app_store_script_user is a sg dict (with name, id and type) 
          representing the script user used to connect to the app store.
        
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
                


class SetupProjectWizard(object):
    """
    A class which wraps around the project setup functionality in toolkit
    """
    
    def __init__(self, log, sg, sg_app_store, sg_app_store_script_user):
        """
        Constructor. 
        """        
        self._params = ProjectSetupParameters(log, sg, sg_app_store, sg_app_store_script_user)
        self._sg = sg
        self._sg_app_store = sg_app_store
        self._sg_app_store_script_user = sg_app_store_script_user

        
    def set_project(self, project_id, force=False):
        """
        Specify which project that should be set up.
        
        :param project_id: Shotgun id for the project that should be set up.
        :param force: Allow for the setting up of existing projects.
        """
        self._params.set_project_id(project_id, force)        
        
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
        
        This method will validate the configuration and ensure that all required
        storages needed by the configuration exists and are correctly set up.
        
        Returns a dictionary with config metadata:
        
        {"display_name": "Default Config",
         "description": "Short description in the configuration",  
         "storage": { "primary": { "description": "Where project files are saved", 
                                    "exists": True,
                                    "valid" : False,
                                    "message": "cannot find the local path /foo/bar"}}
        
        :param config_uri: string describing a path on disk, a github uri or the name of an app store config.
        :returns: a dictionary representing the configuration, see above for details.
        """
        self._params.set_config_uri(config_uri)
        
        config_info = {}
        
        config_info["display_name"] = self._params.get_configuration_name()
        config_info["description"] = self._params.get_configuration_decsription()
        config_info["storages"] = {}
        
        
        for s in self._params.get_required_storages():
            storage_data = {}
            storage_data["description"]
        

    def get_default_project_disk_name(self):
        """
        Returns a default project name from toolkit.
        
        Before you call this method, a config and a project must have been set.
        
        This will execute hooks etc and given the selected project id will
        return a suggested project name.
        
        :returns: string with a suggested project name
        """
        return self._params.get_project_disk_name()
        
    def validate_project_disk_name(self, project_name):
        """
        Validate the project disk name.
        Raises Exceptions if the project disk name is not valid.
        """
        self._params.validate_project_disk_name(project_name)
        
    def preview_project_paths(self, project_name):
        """
        Return preview project paths given a project name.
        
        { "primary": { "darwin": "/foo/bar/project_name", 
                       "linux2": "/foo/bar/project_name",
                       "win32" : "c:\foo\bar\project_name"},
          "textures": { "darwin": "/textures/project_name", 
                        "linux2": "/textures/project_name",
                        "win32" : "c:\textures\project_name"}}
        
        The operating systems are enumerated using sys.platform jargon.
        
        :param project_name: string with a project name.
        :returns: Dictionary, see above.
        """
        return_data = {}
        for s in self._params.get_required_storages():
            return_data[s] = {}
            return_data[s]["darwin"] = self._params.preview_project_path(s, project_name, "darwin")
            return_data[s]["win32"] = self._params.preview_project_path(s, project_name, "win32")
            return_data[s]["linux2"] = self._params.preview_project_path(s, project_name, "linux2") 
        
        return return_data
        
    def set_project_disk_name(self, set_project_disk_name):
        """
        Set the desired name of the project.
        May raise exception if the name is not valid.
        
        :param set_project_disk_name: string with a project name.
        """
        self._params.set_project_disk_name(set_project_disk_name)
    
    def get_default_configuration_location(self):
        """
        Returns default suggested location for configurations.
        Returns a dictionary with sys.platform style keys linux2/win32/darwin, e.g.
        
        { "darwin": "/foo/bar/project_name", 
          "linux2": "/foo/bar/project_name",
          "win32" : "c:\foo\bar\project_name"}        

        :returns: dictionary with paths
        """
        return self._params.get_default_configuration_location()
    
    def set_configuration_location(self, linux_path, windows_path, macosx_path):
        """
        Specifies where the pipeline configuration should be located.
        
        :param linux_path: Path on linux 
        :param windows_path: Path on windows
        :param macosx_path: Path on mac
        """
        self._params.set_configuration_location(linux_path, windows_path, macosx_path)
    
    def execute(self):
        """
        Execute the actual setup process.
        """
        
        # run overall validation of the project setup
        self._params.validate_project_io()
        self._params.validate_config_io()
        
        # and finally carry out the setup
        return run_project_setup(self._log, 
                                 self._sg, 
                                 self._sg_app_store, 
                                 self._sg_app_store_script_user, 
                                 self._params)
        
    


    
