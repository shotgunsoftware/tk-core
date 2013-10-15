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
Base class for Abstract classes for Engines, Apps and Frameworks

"""

import os
import sys
import imp
import uuid
from .. import hook
from ..errors import TankError
from . import constants

class TankBundle(object):
    """
    Abstract Base class for any engine, framework app etc in tank
    """

    def __init__(self, tk, context, settings, descriptor):
        """
        Constructor.
        """
        self.__tk = tk
        self.__context = context
        self.__settings = settings
        self.__sg = None
        self.__module_uid = None
        self.__descriptor = descriptor    
        self.__frameworks = {}

        # emit an engine started event
        tk.execute_hook(constants.TANK_BUNDLE_INIT_HOOK_NAME, bundle=self)
        
    ##########################################################################################
    # properties used by internal classes, not part of the public interface
    
    @property
    def descriptor(self):
        """
        Internal method - not part of Tank's public interface.
        This method may be changed or even removed at some point in the future.
        We leave no guarantees that it will remain unchanged over time, so 
        do not use in any app code. 
        """
        return self.__descriptor
    
    @property
    def settings(self):
        """
        Internal method - not part of Tank's public interface.
        This method may be changed or even removed at some point in the future.
        We leave no guarantees that it will remain unchanged over time, so 
        do not use in any app code. 
        """
        return self.__settings
    
    ##########################################################################################
    # methods used by internal classes, not part of the public interface

    def get_setting_from(self, other_settings, key, default=None):
        """
        Internal method - not part of Tank's public interface.
        
        Get a value from the settings dictionary passed in
        using the logic from this application

        :param other_settings: dictionary to use to find setting
        :param key: setting name
        :param default: default value to return
        """
        return self.__resolve_setting_value(key, other_settings.get(key, default))

    def get_template_from(self, other_settings, key):
        """
        Internal method - not part of Tank's public interface.
        
        A shortcut for looking up which template is referenced in the given setting from
        the settings dictionary passed in.  It then calls get_template_by_name() on it.
        
        :param other_settings: dictionary to use to find setting
        :param key: setting name
        """
        template_name = self.get_setting_from(other_settings, key)        
        return self.get_template_by_name(template_name)

    def execute_hook_from(self, other_settings, key, **kwargs):
        """
        Internal method - not part of Tank's public interface.
        
        Shortcut for grabbing the hook name used in the settings dictionary 
        passed in and then calling execute_hook_by_name() on it.
        
        :param other_settings: dictionary to use to find setting
        :param key: setting name
        :param **kwargs: arguments to be passed to the hook
        """
        hook_name = self.get_setting_from(other_settings, key)
        return self.__execute_hook_internal(hook_name, key, **kwargs)



    ##########################################################################################
    # properties

    @property
    def name(self):
        """
        The short name for the item (e.g. tk-maya)
        
        :returns: name as string
        """
        return self.__descriptor.get_system_name()
    
    @property
    def display_name(self):
        """
        The displayname for the item (e.g. Maya Engine)
        
        :returns: display name as string
        """
        return self.__descriptor.get_display_name()

    @property
    def description(self):
        """
        A short description of the item
        
        :returns: string
        """
        return self.__descriptor.get_description()

    @property
    def version(self):
        """
        The version of the item (e.g. 'v0.2.3')
        
        :returns: string representing the version
        """
        return self.__descriptor.get_version()

    @property
    def icon_256(self):
        """
        The path to the app's icon, which is a 256px square png
        """
        return self.__descriptor.get_icon_256()

    @property
    def documentation_url(self):
        """
        Return the relevant documentation url for this item.
        
        :returns: url string, None if no documentation was found
        """
        return self.__descriptor.get_doc_url()        

    @property
    def support_url(self):
        """
        Return the relevant support url for this item.
        
        :returns: url string, None if no documentation was found
        """
        return self.__descriptor.get_support_url()        

    @property
    def disk_location(self):
        """
        The folder on disk where this item is located
        """
        path_to_this_file = os.path.abspath(sys.modules[self.__module__].__file__)
        return os.path.dirname(path_to_this_file)

    @property
    def cache_location(self):
        """
        An item-specific location on disk where the app or engine can store
        random cache data. This location is guaranteed to exist on disk.
        """
        # organize caches by app name
        folder = os.path.join(self.__tk.pipeline_configuration.get_path(), "cache", self.name)
        if not os.path.exists(folder):
            # create it using open permissions (not via hook since we want to be in control
            # of permissions inside the tank folders)
            old_umask = os.umask(0)
            os.makedirs(folder, 0777)
            os.umask(old_umask)                
        
        return folder


    @property
    def context(self):
        """
        The current context associated with this item
        
        :returns: context object
        """
        return self.__context

    @property
    def shotgun(self):
        """
        Delegates to the Sgtk API instance's shotgun connection, which is lazily
        created the first time it is requested.
        
        :returns: Shotgun API handle
        """
        return self.__tk.shotgun
    
    @property
    def tank(self):
        """
        Returns an Sgtk API instance associated with this item
        
        :returns: Sgtk API handle 
        """
        return self.__tk
    
    # new name compatibility 
    sgtk = tank
    
    @property
    def frameworks(self):
        """
        List of all frameworks associated with this item
        
        :returns: List of framework objects
        """
        return self.__frameworks
    
    ##########################################################################################
    # public methods

    def import_module(self, module_name):
        """
        Special Tank import command for app modules. Imports the python folder inside
        an app and returns the specified module name that exists inside the python folder.
        
        For more information, see the API documentation.
        """
        # local import to avoid cycles
        from . import framework
        
        # first, set the module we are currently processing
        framework.CURRENT_BUNDLE_DOING_IMPORT.append(self)
        
        try:
        
            # get the python folder
            python_folder = os.path.join(self.disk_location, constants.BUNDLE_PYTHON_FOLDER)
            if not os.path.exists(python_folder):
                raise TankError("Cannot import - folder %s does not exist!" % python_folder)
            
            # and import
            if self.__module_uid is None:
                self.log_debug("Importing python modules in %s..." % python_folder)
                # alias the python folder with a UID to ensure it is unique every time it is imported
                self.__module_uid = uuid.uuid4().hex
                imp.load_module(self.__module_uid, None, python_folder, ("", "", imp.PKG_DIRECTORY) )
            
            # we can now find our actual module in sys.modules as GUID.module_name
            mod_name = "%s.%s" % (self.__module_uid, module_name)
            if mod_name not in sys.modules:
                raise TankError("Cannot find module %s as part of %s!" % (module_name, python_folder))
            
            # lastly, append our own object to the added module. This is to make it easier to 
            # do elegant imports in the class scope via the tank.platform.import_framework method
            sys.modules[mod_name]._tank_bundle = self
        
        finally:
            # no longer processing this one
            framework.CURRENT_BUNDLE_DOING_IMPORT.pop()
        
        return sys.modules[mod_name]

    def __post_process_settings_r(self, key, value, schema):
        """
        Recursive post-processing of settings values
        """
        
        settings_type = schema.get("type")
        
        if settings_type == "list":
            processed_val = []
            value_schema = schema["values"]
            for x in value:
                processed_val.append(self.__post_process_settings_r(key, x, value_schema))
        
        elif settings_type == "dict":
            items = schema.get("items", {})
            # note - we assign the original values here because we 
            processed_val = value
            for (key, value_schema) in items.items():            
                processed_val[key] = self.__post_process_settings_r(key, value[key], value_schema)
            
        
        elif settings_type == "config_path":
            # this is a config path. Stored on the form
            # foo/bar/baz.png, we should translate that into
            # PROJECT_PATH/tank/config/foo/bar/baz.png
            config_folder = self.__tk.pipeline_configuration.get_config_location()
            adjusted_value = value.replace("/", os.path.sep)
            processed_val = os.path.join(config_folder, adjusted_value)
        
        
        elif type(value) == str and value.startswith("hook:"):
            
            # handle the special form where the value is computed in a hook.
            # 
            # if the template parameter is on the form
            # a) hook:foo_bar
            # b) hook:foo_bar:testing:testing
            #        
            # The following hook will be called
            # a) foo_bar with parameters []
            # b) foo_bar with parameters [testing, testing]
            #
            chunks = value.split(":")
            hook_name = chunks[1]
            params = chunks[2:] 
            processed_val = self.__tk.execute_hook(hook_name, 
                                                   setting=key, 
                                                   bundle_obj=self, 
                                                   extra_params=params)

        else:
            # pass-through
            processed_val = value
        
        return processed_val
        
    def __resolve_setting_value(self, key, value):
        """
        Resolve a setting value.  Exposed to allow values
        to be resolved for settings derived outside of the 
        app.
        
        :param key:   setting name
        :param value: setting value
        """
        # try to get the type for the setting
        # (may fail if the key does not exist in the schema,
        # which is an old use case we need to support now...)
        try:
            schema = self.__descriptor.get_configuration_schema().get(key)
        except:
            schema = None
        
        if schema:
            # post process against schema
            value = self.__post_process_settings_r(key, value, schema)
            
        return value

    def get_setting(self, key, default=None):
        """
        Get a value from the item's settings

        :param key: config name
        :param default: default value to return
        """
        return self.__resolve_setting_value(key, self.__settings.get(key, default))
            
    def get_template(self, key):
        """
        A shortcut for looking up which template is referenced in the given setting, and
        calling get_template_by_name() on it.
        """

        template_name = self.get_setting(key)        
        return self.get_template_by_name(template_name)
    
    def get_template_by_name(self, template_name):
        """
        Find the named template.
        """
        return self.tank.templates.get(template_name)
            
    def execute_hook(self, key, **kwargs):
        """
        Shortcut for grabbing the hook name used in the settings, 
        then calling execute_hook_by_name() on it.
        """
        hook_name = self.get_setting(key)
        return self.__execute_hook_internal(hook_name, key, **kwargs)
        
    def __execute_hook_internal(self, hook_name, key, **kwargs):
        """
        Internal method for executing the specified hook.  If hook
        name is constants.TANK_BUNDLE_DEFAULT_HOOK_SETTING it will
        look up the actual hook to use in the manifest, otherwise
        it will assume that the hook lives in the 'hooks' directory
        for the bundle.
        """
        if hook_name == constants.TANK_BUNDLE_DEFAULT_HOOK_SETTING:
            # hook settings points to the default one.
            # find the name of the hook from the manifest
            manifest = self.__descriptor.get_configuration_schema()
            #
            # Entries are on the following form
            #            
            # hook_publish_file:
            #    type: hook
            #    description: Called when a file is published, e.g. copied from a work area to a publish area.
            #    parameters: [source_path, target_path]
            #    default_value: maya_publish_file
            #
            default_hook_name = manifest.get(key).get("default_value", "undefined")
            
            # special case - if the manifest default value contains the special token
            # {engine_name}, replace this with the name of the associated engine.
            # note that this bundle base class level has no notion of what an engine or app is
            # so we basically do this duck-type style, basically see if there is an engine
            # attribute and if so, attempt the replacement:
            if constants.TANK_HOOK_ENGINE_REFERENCE_TOKEN in default_hook_name:
                try:
                    engine_name = self.engine.name
                except:
                    raise TankError("%s: Failed to be able to find the associated engine "
                                    "when trying to access hook %s" % (self, hook_name))
                
                updated_hook_name = default_hook_name.replace(constants.TANK_HOOK_ENGINE_REFERENCE_TOKEN, engine_name)
                hook_path = os.path.join(self.disk_location, "hooks", "%s.py" % updated_hook_name)

                if not os.path.exists(hook_path):
                    # produce user friendly error message
                    raise TankError("%s config setting %s: This hook is using an engine specific "
                                    "hook setup (e.g '%s') but no hook '%s' has been provided with the app. "
                                    "In order for this app to work with engine %s, you need to provide a "
                                    "custom hook implementation. Please contact support for more "
                                    "information" % (self, key, default_hook_name, hook_path, engine_name))
                
            else:
                # no dynamic default value. No need to produce a special error message in this case
                # if the file does not exist - the loader will check too.
                hook_path = os.path.join(self.disk_location, "hooks", "%s.py" % default_hook_name)  
            
            ret_val = hook.execute_hook(hook_path, self, **kwargs)
             
        else:
            # use a specific hook in the user hooks folder
            ret_val = self.execute_hook_by_name(hook_name, **kwargs)
        
        return ret_val

    def execute_hook_by_name(self, hook_name, **kwargs):
        """
        Execute an arbitrary hook located in the hooks folder for this project.
        The hook_name is the name of the python file in which the hook resides,
        without the file extension.
        
        In most use cases, the execute_hook method is the preferred way to 
        access a hook from an app.
        
        This method is typically only used when you want to execute an arbitrary
        list of hooks, for example if you want to run a series of arbitrary
        user defined pre-publish validation hooks.  
        """
        hook_folder = self.tank.pipeline_configuration.get_hooks_location()
        hook_path = os.path.join(hook_folder, "%s.py" % hook_name)
        return hook.execute_hook(hook_path, self, **kwargs)
    
    def ensure_folder_exists(self, path):
        """
        Convenience method to make it easy for apps and engines to create folders
        in a standardized fashion. While the creation of high level folder structure
        such as Shot and Asset folders is typically handled by the folder creation system
        in Tank, Apps tend to need to create leaf-level folders such as publish folders
        and work areas. These are often created just in time of the operation.
        
        :param path: path to create
        """        
        try:
            self.__tk.execute_hook("ensure_folder_exists", path=path, bundle_obj=self)
        except Exception, e:
            raise TankError("Error creating folder %s: %s" % (path, e))
        
        
