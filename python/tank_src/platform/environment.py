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
Environment Settings Object and access.

"""

import os
import sys
import copy

from tank_vendor import yaml
from . import constants
from . import environment_includes
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
    
    def __init__(self, env_path, pipeline_config, context=None):
        """
        Constructor
        """
        self.__env_path = env_path
        self.__env_data = None
        self.__engine_locations = {}
        self.__app_locations = {}
        self.__framework_locations = {}
        self.__context = context
        self.__pipeline_config = pipeline_config
        
        # validate and populate config
        self.__refresh()
        
        
    def __repr__(self):
        return "<Sgtk Environment %s>" % self.__env_path
    
    def __str__(self):
        return "Environment %s" % os.path.basename(self.__env_path)

    def __refresh(self):
        """Refreshes the environment data from disk
        """
        
        if not os.path.exists(self.__env_path):
            raise TankError("Attempting to load non-existent environment file: %s" % self.__env_path)
        
        try:
            env_file = open(self.__env_path, "r")
            data = yaml.load(env_file)
            env_file.close()
        except Exception, exp:
            raise TankError("Could not parse file %s. Error reported: %s" % (self.__env_path, exp))            
     
        self.__env_data = environment_includes.process_includes(self.__env_path, data, self.__context)
        
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
                        
    def __load_data(self, path):
        """
        loads the main data from disk, raw form
        """
        # load the data in 
        try:
            env_file = open(path, "r")
            data = yaml.load(env_file)
            env_file.close()
        except Exception, exp:
            raise TankError("Could not parse file %s. Error reported: %s" % (path, exp))
        
        return data
    
    def __write_data(self, path, data):
        """
        writes the main data to disk, raw form
        """
        try:
            env_file = open(path, "wt")
            yaml.dump(data, env_file)
            env_file.close()
        except Exception, exp:
            raise TankError("Could not write environment file %s. Error reported: %s" % (path, exp))
        
        
    def find_location_for_engine(self, engine_name):
        """
        Returns the filename and a list of dictionary keys where an engine instance resides.
        The dictionary key list (tokens) can be nested, for example
        [engines, tk-maya] or just flat [tk-maya-ref]
        """
        # get the raw data
        root_yml_data = self.__load_data(self.__env_path)
        eng_data = root_yml_data["engines"][engine_name]
        
        if isinstance(eng_data, basestring) and eng_data.startswith("@"):
            # this is a reference - try to load it in!
            token = eng_data[1:]
            tokens = [token]
            yml_file = environment_includes.find_reference(self.__env_path, self.__context, token)
        else:
            tokens = ["engines", engine_name]
            yml_file = self.__env_path 
        
        return (tokens, yml_file)
        
    def find_location_for_framework(self, framework_name):
        """
        Returns the filename and a list of dictionary keys where a framework instance resides.
        The dictionary key list (tokens) can be nested, for example
        [frameworks, tk-frameork-widget_v0.2.x] or just flat [tk-frameork-widget_v0.2.x]
        """
        # get the raw data
        root_yml_data = self.__load_data(self.__env_path)
        fw_data = root_yml_data["frameworks"][framework_name]
        
        if isinstance(fw_data, basestring) and fw_data.startswith("@"):
            # this is a reference - try to load it in!
            token = fw_data[1:]
            tokens = [token]
            yml_file = environment_includes.find_reference(self.__env_path, self.__context, token)
        else:
            tokens = ["frameworks", framework_name]
            yml_file = self.__env_path 
        
        return (tokens, yml_file)
         
    def find_location_for_app(self, engine_name, app_name):
        """
        Returns the filename and the dictionary key where an app instance resides.
        The dictionary key list (tokens) can be nested, for example
        [engines, tk-maya, apps, tk-multi-about] or just flat [tk-mylti-about-def]
        """
        
        (engine_tokens, engine_yml_file) = self.find_location_for_engine(engine_name)

        # now update the yml file where the engine is defined
        engine_yml_data = self.__load_data(engine_yml_file)
        
        # now the token may be either "my-maya-ref" or "engines/tk-maya"
        # find the right chunk in the file
        
        # track the location of our app in the yml hierarchy
        # (e..g ["engines", "tk-maya"] 
        engine_data = engine_yml_data
        for x in engine_tokens:
            engine_data = engine_data.get(x)
        
        app_tokens = engine_tokens
        app_yml_file = engine_yml_file
                        
        # now that we have found the file in which the engine is defined, 
        # find the file where the app is defined
        app_section = engine_data["apps"]
        if isinstance(app_section, basestring) and app_section.startswith("@"):
            # whole app section is a reference!
            app_section_token = app_section[1:]
            app_yml_file = environment_includes.find_reference(app_yml_file, self.__context, app_section_token)
            app_yml_data = self.__load_data(app_yml_file)
            app_data = app_yml_data[app_section_token]
            app_tokens = [app_section_token]
        else:
            # found an apps section:
            app_tokens.append("apps")
            app_data = app_section[app_name]
        
        if isinstance(app_data, basestring) and app_data.startswith("@"):
            # this is a reference!
            # now we are at the top of the token stack again because we switched files
            app_token = app_data[1:]
            app_tokens = [app_token]
            app_yml_file = environment_includes.find_reference(app_yml_file, self.__context, app_token)
        else:
            # app is defined in current file
            app_tokens.append(app_name)

        return (app_tokens, app_yml_file)
            
    def update_engine_settings(self, engine_name, new_data, new_location):
        """
        Updates the engine configuration
        """
        if engine_name not in self.__env_data["engines"]:
            raise TankError("Engine %s does not exist in environment %s" % (engine_name, self.__env_path) )
        
        (tokens, yml_file) = self.find_location_for_engine(engine_name)
        
        # now update the yml file where the engine is defined
        yml_data = self.__load_data(yml_file)
        
        # now the token may be either [my-maya-ref] or [engines, tk-maya]
        # find the right chunk in the file
        engine_data = yml_data 
        for x in tokens:
            engine_data = engine_data.get(x)
        
        if new_location:
            engine_data[constants.ENVIRONMENT_LOCATION_KEY] = new_location

        self._update_settings_recursive(engine_data, new_data)
        self.__write_data(yml_file, yml_data)
        
        # sync internal data with disk
        self.__refresh()
            
        
    def update_app_settings(self, engine_name, app_name, new_data, new_location):
        """
        Updates the app configuration.
        """
        if engine_name not in self.__env_data["engines"]:
            raise TankError("Engine %s does not exist in environment %s" % (engine_name, self.__env_path) )
        if app_name not in self.__env_data["engines"][engine_name]["apps"]:
            raise TankError("App %s.%s does not exist in environment %s" % (engine_name, app_name, self.__env_path) )
        
        (tokens, yml_file) = self.find_location_for_app(engine_name, app_name)
        
        # now update the yml file where the engine is defined
        yml_data = self.__load_data(yml_file)
        
        # now the token may be either [my-maya-ref] or [engines, tk-maya]
        # find the right chunk in the file
        app_data = yml_data 
        for x in tokens:
            app_data = app_data.get(x)
        
        # finally update the file        
        app_data[constants.ENVIRONMENT_LOCATION_KEY] = new_location
        self._update_settings_recursive(app_data, new_data)
        self.__write_data(yml_file, yml_data)
        
        # sync internal data with disk
        self.__refresh()
        
    def update_framework_settings(self, framework_name, new_data, new_location):
        """
        Updates the framework configuration
        """
        if framework_name not in self.__env_data["frameworks"]:
            raise TankError("Framework %s does not exist in environment %s" % (framework_name, self.__env_path) )
        
        (tokens, yml_file) = self.find_location_for_framework(framework_name)
        
        # now update the yml file where the engine is defined
        yml_data = self.__load_data(yml_file)
        
        # now the token may be either [my_fw_ref] or [frameworks, tk-framework-widget_v0.1.x]
        # find the right chunk in the file
        framework_data = yml_data 
        for x in tokens:
            framework_data = framework_data.get(x)
        
        if new_location:
            framework_data[constants.ENVIRONMENT_LOCATION_KEY] = new_location

        self._update_settings_recursive(framework_data, new_data)
        self.__write_data(yml_file, yml_data)
        
        # sync internal data with disk
        self.__refresh()
        
        
    def _update_settings_recursive(self, settings, new_data):
        """
        Recurse through new data passed in and update settings structure accordingly.
        
        :param settings: settings dictionary to update with the new values
        :parma new_data: new settings data to update into the settings dictionary
        """
        for name, data in new_data.iteritems():
            # if data is a dictionary then we may need to recurse to update nested settings:
            if isinstance(data, dict):
                setting = settings.get(name)
                if setting:
                    if isinstance(setting, list):
                        # need to handle a list of dictionaries so update
                        # each item in the list with the new data:
                        for item in setting:
                            if isinstance(item, dict):
                                # make sure we have a unique instance of the data 
                                # for each item in the list
                                item_data = copy.deepcopy(data)
                                # recurse:
                                self._update_settings_recursive(item, item_data)
                            else:
                                # setting type doesn't match data type so skip!
                                pass
                                
                    elif isinstance(setting, dict):
                        # recurse:
                        self._update_settings_recursive(setting, data)
                    else:
                        # setting type doesn't match data type so skip!
                        pass
                else:
                    # setting didn't exist before so just add it:
                    settings[name] = data
                    
            else:
                # add new or update existing setting:
                settings[name] = data
            
    def create_framework_settings(self, yml_file, framework_name, params, location):
        """
        Creates new framework settings.        
        """
        
        data = self.__load_data(yml_file)
        
        if data.get("frameworks") is None:
            data["frameworks"] = {}
        
        if framework_name in data["frameworks"]:
            raise TankError("Framework %s already exists in environment %s" % (framework_name, yml_file) )
        
        data["frameworks"][framework_name] = {}
        data["frameworks"][framework_name][constants.ENVIRONMENT_LOCATION_KEY] = location
        self._update_settings_recursive(data["frameworks"][framework_name], params)
        
        self.__write_data(yml_file, data)
        # sync internal data with disk
        self.__refresh()

        
    def create_engine_settings(self, engine_name):
        """
        Creates a new engine settings chunk in the root file of the env tree.
        """
        
        data = self.__load_data(self.__env_path)
        
        if engine_name in data["engines"]:
            raise TankError("Engine %s already exists in environment %s" % (engine_name, self.__env_path) )
        
        data["engines"][engine_name] = {}
        # and make sure we also create the location key
        data["engines"][engine_name][constants.ENVIRONMENT_LOCATION_KEY] = {}
        # and make sure we also create the apps key
        data["engines"][engine_name]["apps"] = {}
        
        self.__write_data(self.__env_path, data)
        # sync internal data with disk
        self.__refresh()
        
        
    def create_app_settings(self, engine_name, app_name):
        """
        Creates a new app settings chunk in the root file of the env tree.
        """
        
        data = self.__load_data(self.__env_path)
        
        # check that the engine name exists in the config
        if engine_name not in data["engines"]:
            raise TankError("Engine %s does not exist in environment %s" % (engine_name, self.__env_path) )

        # it is possible that the whole engine is referenced via an @include. In this case, 
        # raise an error. Here's an example structure of what that looks like:
        #
        # engines:
        #   tk-houdini: '@tk-houdini-shot'
        #   tk-maya: '@tk-maya-shot-lighting'
        #   tk-motionbuilder: '@tk-motionbuilder-shot'
        engines_section = data["engines"][engine_name]
        if isinstance( engines_section, str) and engines_section.startswith("@"):
            raise TankError("The configuration for engine '%s' located in the environment file '%s' has a "
                            "refererence to another file ('%s'). This type "
                            "of configuration arrangement cannot currently be automatically " 
                            "modified - please edit it by hand!" % (engine_name, self.__env_path, engines_section))

        # it is possible that the 'apps' dictionary is actually an @include - in this case, raise an error
        # Here's an example of what this looks like:
        #
        # tk-maya:
        #   apps: '@maya_apps'
        #   debug_logging: false
        #   location: {name: tk-maya, type: app_store, version: v0.3.9}
        #   menu_favourites:
        #   - {app_instance: tk-multi-workfiles, name: Shotgun File Manager...}
        #   - {app_instance: tk-multi-snapshot, name: Snapshot...}
        #   - {app_instance: tk-multi-workfiles, name: Shotgun Save As...}
        #   - {app_instance: tk-multi-publish, name: Publish...}
        #   template_project: shot_work_area_maya
        apps_section = data["engines"][engine_name]["apps"]
        if isinstance( apps_section, str) and apps_section.startswith("@"):
            raise TankError("The configuration for engine '%s' located in the environment file '%s' has an "
                            "apps section which is referenced from another file ('%s'). This type "
                            "of configuration arrangement cannot currently be automatically " 
                            "modified - please edit it by hand!" % (engine_name, self.__env_path, apps_section))
        
        # check that it doesn't already exist
        if app_name in apps_section:
            raise TankError("App %s.%s already exists in environment %s" % (engine_name, app_name, self.__env_path) )
        
        
        data["engines"][engine_name]["apps"][app_name] = {}
        # and make sure we also create the location key
        data["engines"][engine_name]["apps"][app_name][constants.ENVIRONMENT_LOCATION_KEY] = {}
    
        self.__write_data(self.__env_path, data)
        # sync internal data with disk
        self.__refresh()
    
