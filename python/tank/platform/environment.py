"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Environment Settings Object and access.

"""

import os
import sys
import copy

from tank_vendor import yaml
from . import constants
from ..errors import TankError
from ..deploy import descriptor


class Environment(object):
    """
    This class encapsulates an environment file and provides a set of methods
    for quick and easy extraction of data from the environment and metadata 
    about the different parts of the confguration (by pulling the info.yml
    files from the various apps and engines referenced in the environment file)
    
    Don't construct this class by hand! Instead, use the 
    pipelineConfiguration.get_environment() method.
    
    """
    
    def __init__(self, env_path, pipeline_config):
        """
        Constructor
        """
        self.__env_path = env_path
        self.__env_data = None
        self.__engine_locations = {}
        self.__app_locations = {}
        self.__framework_locations = {}
        
        # validate and populate config
        self.__refresh()
        
        # pc path for this environment
        self.__pipeline_config = pipeline_config
        
    def __repr__(self):
        return "<Tank Environment %s>" % self.__env_path
    
    def __refresh(self):
        """Refreshes the environment data from disk
        """
        
        if not os.path.exists(self.__env_path):
            raise TankError("Attempting to load non-existent environment file: %s" % self.__env_path)
        
        try:
            env_file = open(self.__env_path, "r")
            try:
                self.__env_data = yaml.load(env_file)
            finally:
                env_file.close()
        except Exception, exp:
            raise TankError("Could not parse file %s. "
                            "Error reported from parser: %s" % (self.__env_path, exp))
     
        if not self.__env_data:
            raise TankError('No data in env file: %s' % (self.__env_path))
    
        if "engines" not in self.__env_data:
            raise TankError("No 'engines' section in env file: %s" % (self.__env_path))
        
        # now organize the data in dictionaries
        
        # framework settings are keyed by fw name
        self.__framework_settings = {}
        # engine settings are keyed by engine name
        self.__engine_settings = {}
        # app settings are keyed by tuple (engine_name, app_name)
        self.__app_settings = {}
        
        # populate the above data structures
        # pass a copy of the data since process is destructive
        d = copy.deepcopy(self.__env_data)
        self.__process_engines(d)
        
        if "frameworks" in self.__env_data:
            # there are frameworks defined! Process them
            d = copy.deepcopy(self.__env_data)
            self.__process_frameworks(d)
        
        # now extract the location key for all the configs
        # these two dicts are keyed in the same way as the settings dicts
        self.__engine_locations = {}
        self.__app_locations = {}
        self.__framework_locations = {}
        self.__extract_locations()
            
    def __is_item_disabled(self, settings):
        """
        handles the checks to see if an item is disabled
        """
        location_dict = settings.get(constants.ENVIRONMENT_LOCATION_KEY)
        
        # Check for disabled and deny_platforms
        is_disabled = location_dict.get("disabled", False)
        if is_disabled:
            return True
        
        # now check if the current platform is disabled
        deny_platforms = location_dict.get("deny_platforms", [])
        # current os: linux/mac/windows
        nice_system_name = {"linux2": "linux", "darwin": "mac", "win32": "windows"}[sys.platform]
        if nice_system_name in deny_platforms:
            return True
        
        return False

    def __process_apps(self, engine, data):
        """
        Populates the __app_settings dict
        """
        if data is None:
            return
        # iterate over the apps dict
        for app, app_settings in data.items():
            if not self.__is_item_disabled(app_settings):
                self.__app_settings[(engine, app)] = app_settings
    
    def __process_engines(self, data):
        """
        Populates the __engine_settings dict
        """
        # assumes that there is an engines key in the data dict
        engines = data.pop("engines")
        if engines is None:
            return
        # iterate over the engine dict
        for engine, engine_settings in engines.items():
            # Check for engine disabled
            if not self.__is_item_disabled(engine_settings):
                engine_apps = engine_settings.pop('apps')
                self.__process_apps(engine, engine_apps)
                self.__engine_settings[engine] = engine_settings
    
    def __process_frameworks(self, data):
        """
        Populates the __frameworks_settings dict
        """
        # assumes that there is an frameworks key in the data dict
        frameworks = data.pop("frameworks")
        if frameworks is None:
            return

        # iterate over the engine dict
        for fw, fw_settings in frameworks.items():
            # Check for engine disabled
            if not self.__is_item_disabled(fw_settings):
                self.__framework_settings[fw] = fw_settings

    def __extract_locations(self):
        """
        Extract (remove from settings) the location key into the two separate structures
        self.__engine_locations
        self.__app_locations
        self.__framework_locations
        """

        for fw in self.__framework_settings:
            location_dict = self.__framework_settings[fw].get(constants.ENVIRONMENT_LOCATION_KEY)
            if location_dict is None:
                raise TankError("The environment %s does not have a valid location " 
                                "key for framework %s" % (self.__env_path, fw))
            # remove location from dict
            self.__framework_locations[fw] = self.__framework_settings[fw].pop(constants.ENVIRONMENT_LOCATION_KEY)

        for eng in self.__engine_settings:
            location_dict = self.__engine_settings[eng].get(constants.ENVIRONMENT_LOCATION_KEY)
            if location_dict is None:
                raise TankError("The environment %s does not have a valid location " 
                                "key for engine %s" % (self.__env_path, eng))
            # remove location from dict
            self.__engine_locations[eng] = self.__engine_settings[eng].pop(constants.ENVIRONMENT_LOCATION_KEY)
        
        for (eng, app) in self.__app_settings:
            location_dict = self.__app_settings[(eng,app)].get(constants.ENVIRONMENT_LOCATION_KEY)
            if location_dict is None:
                raise TankError("The environment %s does not have a valid location " 
                                "key for app %s.%s" % (self.__env_path, eng, app))
            # remove location from dict
            self.__engine_locations[(eng,app)] = self.__app_settings[(eng,app)].pop(constants.ENVIRONMENT_LOCATION_KEY)
        
        
    
    ##########################################################################################
    # Properties

    @property
    def name(self):
        """
        returns the environment name, e.g. the file name of the environment file
        without its extension
        """
        file_name_with_ext = os.path.basename(self.__env_path)
        (file_name, ext) = os.path.splitext(file_name_with_ext)
        return file_name

    @property
    def description(self):
        """
        Returns a description of this environment
        """
        return self.__env_data.get("description", "No description found.")
        
    @property
    def disk_location(self):
        """
        Returns a path to this environment
        """
        return self.__env_path


    ##########################################################################################
    # Public methods - data retrieval

    def get_engines(self):
        """
        Returns all the engines contained in this environment file
        """
        return self.__engine_settings.keys()
        
    def get_frameworks(self):
        """
        Returns all the frameworks contained in this environment file
        """
        return self.__framework_settings.keys()

    def get_apps(self, engine):
        """
        Returns all apps for an engine contained in this environment file
        """
        if engine not in self.get_engines():
            raise TankError("Engine '%s' is not part of environment %s" % (engine, self.__env_path))
        
        apps = []
        engine_app_tuples = self.__app_settings.keys()
        for (engine_name, app_name) in engine_app_tuples:
            if engine_name == engine:
                apps.append(app_name)
        return apps
        
    def get_framework_settings(self, framework):
        """
        Returns the settings for a framework
        """
        d = self.__framework_settings.get(framework)
        if d is None:
            raise TankError("Framework '%s' is not part of environment %s" % (framework, self.__env_path))        
        return d

    def get_engine_settings(self, engine):
        """
        Returns the settings for an engine
        """
        d = self.__engine_settings.get(engine)
        if d is None:
            raise TankError("Engine '%s' is not part of environment %s" % (engine, self.__env_path))        
        return d
        
    def get_app_settings(self, engine, app):
        """
        Returns the settings for an app
        """
        key = (engine, app)
        d = self.__app_settings.get(key)
        if d is None:
            raise TankError("App '%s.%s' is not part of environment %s" % (engine, app, self.__env_path))
        return d
        
    def get_framework_descriptor(self, framework_name):
        """
        Returns the descriptor object for a framework.
        """
        location_dict = self.__framework_locations.get(framework_name)
        if location_dict is None:
            raise TankError("The framework %s does not have a valid location " 
                            "key for engine %s" % (self.__env_path, framework_name))

        # get the descriptor object for the location
        d = descriptor.get_from_location(descriptor.AppDescriptor.FRAMEWORK, 
                                         self.__pipeline_config, 
                                         location_dict)
        
        return d        
        
    def get_engine_descriptor(self, engine_name):
        """
        Returns the descriptor object for an engine.
        """
        location_dict = self.__engine_locations.get(engine_name)
        if location_dict is None:
            raise TankError("The environment %s does not have a valid location " 
                            "key for engine %s" % (self.__env_path, engine_name))

        # get the descriptor object for the location
        d = descriptor.get_from_location(descriptor.AppDescriptor.ENGINE, 
                                         self.__pipeline_config, 
                                         location_dict)
        
        return d
        
    def get_app_descriptor(self, engine_name, app_name):
        """
        Returns the descriptor object for an app.
        """
        
        location_dict = self.__engine_locations.get( (engine_name, app_name) )
        if location_dict is None:
            raise TankError("The environment %s does not have a valid location " 
                            "key for app %s.%s" % (self.__env_path, engine_name, app_name))
        
        # get the version object for the location
        d = descriptor.get_from_location(descriptor.AppDescriptor.APP, 
                                         self.__pipeline_config,
                                         location_dict)
        
        return d
        
    ##########################################################################################
    # Public methods - data update
    
    # todo - add methods to check time stamps so that we can detect if someone else 
    # is making changes!
    def __update_file_on_disk(self):
        """
        Updates the file on disk
        """
        try:
            env_file = open(self.__env_path, "wt")
            yaml.dump(self.__env_data, env_file)
            env_file.close()
        except Exception, exp:
            raise TankError("Could not write to environment file %s. "
                            "Error reported: %s" % (self.__env_path, exp))
        
        # sync internal data with disk
        self.__refresh()

    def update_framework_location(self, framework_name, new_location):
        """
        Updates the location dictionary for a framework
        """
        if self.__env_data.get("frameworks") is None:
            self.__env_data["frameworks"] = {}
            
        if framework_name not in self.__env_data.get("frameworks"):
            raise TankError("Framework %s does not exist in environment %s" % (framework_name, self.__env_path) )
        
        self.__env_data["frameworks"][framework_name][constants.ENVIRONMENT_LOCATION_KEY] = new_location
        self.__update_file_on_disk()
    
    def update_engine_location(self, engine_name, new_location):
        """
        Updates the location dictionary for an engine
        """
        if engine_name not in self.__env_data["engines"]:
            raise TankError("Engine %s does not exist in environment %s" % (engine_name, self.__env_path) )
        
        self.__env_data["engines"][engine_name][constants.ENVIRONMENT_LOCATION_KEY] = new_location
        self.__update_file_on_disk()
        
    def update_app_location(self, engine_name, app_name, new_location):
        """
        Updates the location dictionary for an engine
        """
        if engine_name not in self.__env_data["engines"]:
            raise TankError("Engine %s does not exist in environment %s" % (engine_name, self.__env_path) )
        if app_name not in self.__env_data["engines"][engine_name]["apps"]:
            raise TankError("App %s.%s does not exist in environment %s" % (engine_name, app_name, self) )
        
        self.__env_data["engines"][engine_name]["apps"][app_name][constants.ENVIRONMENT_LOCATION_KEY] = new_location        
        self.__update_file_on_disk()
        
    def update_framework_settings(self, framework_name, new_data):
        """
        Updates the framework configuration
        """
        if self.__env_data.get("frameworks") is None:
            self.__env_data["frameworks"] = {}
        
        if framework_name not in self.__env_data["frameworks"]:
            raise TankError("Framework %s does not exist in environment %s" % (framework_name, self.__env_path) )
        
        data = self.__env_data["frameworks"][framework_name]
        data.update(new_data)
        self.__update_file_on_disk()
    
    def update_engine_settings(self, engine_name, new_data):
        """
        Updates the engine configuration
        """
        if engine_name not in self.__env_data["engines"]:
            raise TankError("Engine %s does not exist in environment %s" % (engine_name, self.__env_path) )
        
        data = self.__env_data["engines"][engine_name]
        data.update(new_data)
        self.__update_file_on_disk()
        
    def update_app_settings(self, engine_name, app_name, new_data):
        """
        Updates the app configuration
        """
        if engine_name not in self.__env_data["engines"]:
            raise TankError("Engine %s does not exist in environment %s" % (engine_name, self.__env_path) )
        if app_name not in self.__env_data["engines"][engine_name]["apps"]:
            raise TankError("App %s.%s does not exist in environment %s" % (engine_name, app_name, self.__env_path) )
        
        data = self.__env_data["engines"][engine_name]["apps"][app_name]
        data.update(new_data)
        self.__update_file_on_disk()
            
    def create_framework_settings(self, framework_name):
        """
        Creates a new empty framework settings in the config
        """
        if self.__env_data.get("frameworks") is None:
            self.__env_data["frameworks"] = {}
        
        if framework_name in self.__env_data["frameworks"]:
            raise TankError("Framework %s already exists in environment %s" % (framework_name, self.__env_path) )
        
        self.__env_data["frameworks"][framework_name] = {}
        # and make sure we also create the location key
        self.__env_data["frameworks"][framework_name][constants.ENVIRONMENT_LOCATION_KEY] = {}
        self.__update_file_on_disk()
            
    def create_engine_settings(self, engine_name):
        """
        Creates a new empty engine settings in the config
        """
        if engine_name in self.__env_data["engines"]:
            raise TankError("Engine %s already exists in environment %s" % (engine_name, self.__env_path) )
        
        self.__env_data["engines"][engine_name] = {}
        # and make sure we also create the location key
        self.__env_data["engines"][engine_name][constants.ENVIRONMENT_LOCATION_KEY] = {}
        # and make sure we also create the apps key
        self.__env_data["engines"][engine_name]["apps"] = {}
        self.__update_file_on_disk()
        
    def create_app_settings(self, engine_name, app_name):
        """
        Creates a new empty app configuration
        """
        if engine_name not in self.__env_data["engines"]:
            raise TankError("Engine %s does not exist in environment %s" % (engine_name, self.__env_path) )
        if app_name in self.__env_data["engines"][engine_name]["apps"]:
            raise TankError("App %s.%s already exists in environment %s" % (engine_name, app_name, self.__env_path) )
        
        self.__env_data["engines"][engine_name]["apps"][app_name] = {}
        # and make sure we also create the location key
        self.__env_data["engines"][engine_name]["apps"][app_name][constants.ENVIRONMENT_LOCATION_KEY] = {}
        self.__update_file_on_disk()
    
