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
import re
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

    def __init__(self, tk, context, settings, descriptor, env):
        """
        Constructor.
        """
        self.__tk = tk
        self.__context = context
        self.__settings = settings
        self.__sg = None
        self.__cache_location = None
        self.__module_uid = None
        self.__descriptor = descriptor    
        self.__frameworks = {}
        self.__environment = env

        # emit an engine started event
        tk.execute_core_hook(constants.TANK_BUNDLE_INIT_HOOK_NAME, bundle=self)
        
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
    def style_constants(self):
        """
        Returns a dictionary of style constants. These can be used to build
        UIs using standard colors and other style components. All keys returned
        in this dictionary can also be used inside a style.qss that lives 
        at the root level of the app, engine or framework. Use a 
        {{DOUBLE_BACKET}} syntax in the stylesheet file, for example:
        
            QWidget
            { 
                color: {{SG_FOREGROUND_COLOR}};
            }
        
        This property returns the values for all constants, for example:
        
            { 
              "SG_HIGHLIGHT_COLOR": "#18A7E3",
              "SG_ALERT_COLOR": "#FC6246",
              "SG_FOREGROUND_COLOR": "#C8C8C8"
            }
        
        :returns: Dictionary. See above for example 
        """
        return constants.SG_STYLESHEET_CONSTANTS    

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
        # this method is memoized for performance since it is being called a lot!
        if self.__cache_location is None:
            # Site configuration's project id is None. Since we're calling a hook, we'll have to
            # pass in 0 to avoid client code crashing because it expects an integer and not
            # the None object. This happens when we are building the cache root, where %d is used to
            # inject the project id in the file path.        
            if self.__tk.pipeline_configuration.is_site_configuration():
                project_id = 0
            else:
                project_id = self.__tk.pipeline_configuration.get_project_id()
            
            pc_id = self.__tk.pipeline_configuration.get_shotgun_id()
            
            self.__cache_location = self.__tk.execute_core_hook_method(constants.CACHE_LOCATION_HOOK_NAME,
                                                                       "bundle_cache",
                                                                       project_id=project_id,
                                                                       pipeline_configuration_id=pc_id,
                                                                       bundle=self)
        
        return self.__cache_location

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


    def get_setting(self, key, default=None):
        """
        Get a value from the item's settings

        :param key: config name
        :param default: default value to return
        """
        return self.__resolve_setting_value(key, self.__settings.get(key, default))
            
    def get_template(self, key):
        """
        Returns a template object for a particular template setting in the Framework configuration.
        This method will look at the app configuration, determine which template is being referred to 
        in the setting, go into the main platform Template API and fetch that particular template object.
    
        This is a convenience method. Shorthand for `self.sgtk.templates[ self.get_setting(key) ]`.
        """
        template_name = self.get_setting(key)        
        return self.get_template_by_name(template_name)
    
    def get_template_by_name(self, template_name):
        """
        Note: This is for advanced use cases - Most of the time you should probably use 
        get_template(). Find a particular template, the way it is named in the master 
        config file templates.yml. This method will access the master templates file 
        directly and pull out a specifically named template without using the app config. 
        Note that using this method may result in code which is less portable across 
        studios, since it makes assumptions about how templates are named and defined in 
        the master config. Generally speaking, it is often better to access templates using 
        the app configuration and the get_template() method.
        
        This is a convenience method. Shorthand for `self.sgtk.templates[template_name]`.
        """
        return self.tank.templates.get(template_name)
                        
    def execute_hook(self, key, **kwargs):
        """
        Execute a hook that is part of the environment configuration for the current bundle.
        
        You simply pass the name of the hook setting that you want to execute and 
        the accompanying arguments, and toolkit will find the correct hook file based
        on the currently configured setting and then execute the execute() method for 
        that hook. 
        
        :param key: The name of the hook setting you want to execute.
        """
        hook_name = self.get_setting(key)
        return self.__execute_hook_internal(key, hook_name, None, **kwargs)
        
    def execute_hook_method(self, key, method_name, **kwargs):
        """
        Execute a specific method in a hook that is part of the 
        environment configuration for the current bundle.
        
        You simply pass the name of the hook setting that you want to execute, the 
        name of the method you want to execute and the accompanying arguments. 
        Toolkit will find the correct hook file based on the currently configured 
        setting and then execute the specified method.
        
        :param key: The name of the hook setting you want to execute.
        :param method_name: Name of the method to execute
        """
        hook_name = self.get_setting(key)
        return self.__execute_hook_internal(key, hook_name, method_name, **kwargs)

    def execute_hook_expression(self, hook_expression, method_name, **kwargs):
        """
        Execute an arbitrary hook via an expression. While the methods execute_hook
        and execute_hook_method allows you to execute a particular hook setting as
        specified in the app configuration manifest, this methods allows you to 
        execute a hook directly by passing a hook expression, for example 
        {config}/path/to/my_hook.py
        
        This is useful if you are doing rapid app development and don't necessarily
        want to expose a hook as a configuration setting just yet. It is also useful 
        if you have app settings that are nested deep inside of lists or dictionaries.
        In that case, you cannot use execute_hook, but instead will have to retrieve
        the value specifically and then run it.
        
        Supported formats:
        
        - hook_expression: {$HOOK_PATH}/path/to/foo.py  -- expression based around an environment variable.
        - hook_expression: {self}/path/to/foo.py -- looks in the hooks folder in the local app, engine of framework.
        - hook_expression: {config}/path/to/foo.py -- Looks in the hooks folder in the project config.
        - hook_expression: {tk-framework-perforce_v1.x.x}/path/to/foo.py -- looks in the hooks folder of a
          framework instance that exists in the current environment. Basically, each entry inside the 
          frameworks section in the current environment can be specified here - all these entries are 
          on the form frameworkname_versionpattern, for example tk-framework-widget_v0.1.2 or 
          tk-framework-shotgunutils_v1.3.x. 
        
        Supported legacy formats:
        
        - hook_expression: foo -- Will look for a foo.py file in the project configuration folder. 

        :param hook_expression: Path to hook to execute. See above for syntax details.
        :param method_name: Method inside the hook to execute.
        """
        return self.__execute_hook_internal(None, hook_expression, method_name, **kwargs)

    def execute_hook_by_name(self, hook_name, **kwargs):
        """
        Note: Now deprecated - Please use execute_hook_expression instead.
        
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
            self.__tk.execute_core_hook("ensure_folder_exists", path=path, bundle_obj=self)
        except Exception, e:
            raise TankError("Error creating folder %s: %s" % (path, e))
        


    ##########################################################################################
    # internal helpers

    def __resolve_hook_path(self, settings_name, hook_expression):
        """
        Resolves a hook settings path into an absolute path.
        
        :param settings_name: The name of the hook setting in the configuration. If the 
                              hook expression passed in to this method is not directly
                              associated with a configuration setting, for example if it
                              comes from a nested settings structure and is resolved via 
                              execute_hook_by_name, this parameter will be None. 
                               
        :param hook_expression: The hook expression value that should be resolved.
        
        :returns: A full path to a hook file.
        """

        if hook_expression is None:
            raise TankError("%s config setting %s: Configuration value cannot be None!" % (self, settings_name))
        
        path = None
        
        # first the default case
        if hook_expression == constants.TANK_BUNDLE_DEFAULT_HOOK_SETTING:
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
            default_hook_name = manifest.get(settings_name).get("default_value", "undefined")
            
            # special case - if the manifest default value contains the special token
            # {engine_name}, replace this with the name of the associated engine.
            # note that this bundle base class level has no notion of what an engine or app is
            # so we basically do this duck-type style, basically see if there is an engine
            # attribute and if so, attempt the replacement:
            engine_name = None
            resolved_hook_name = default_hook_name
            if constants.TANK_HOOK_ENGINE_REFERENCE_TOKEN in default_hook_name:
                try:
                    # note - this technically violates the generic nature of the bundle
                    # base class implementation (because the engine member is not defined in bundle
                    # but in App and Framework but NOT in the Engine class) - an engine trying to define
                    # a hook using the {engine_name} construct will therefore get an error.
                    engine_name = self.engine.name
                except:
                    raise TankError("%s: Failed to find the associated engine "
                                    "when trying to access hook %s" % (self, hook_expression))
                
                resolved_hook_name = default_hook_name.replace(constants.TANK_HOOK_ENGINE_REFERENCE_TOKEN, engine_name)
                
            # get the full path for the resolved hook name:
            if resolved_hook_name.startswith("{self}"):
                # new format hook: 
                #  default_value: '{self}/my_hook.py'
                hooks_folder = os.path.join(self.disk_location, "hooks")
                path = resolved_hook_name.replace("{self}", hooks_folder)
                path = path.replace("/", os.path.sep)
            else:
                # old style hook: 
                #  default_value: 'my_hook'
                path = os.path.join(self.disk_location, "hooks", "%s.py" % resolved_hook_name)
            
            # if the hook uses the engine name then output a more useful error message if a hook for 
            # the engine can't be found.
            if engine_name and not os.path.exists(path):
                # produce user friendly error message
                raise TankError("%s config setting %s: This hook is using an engine specific "
                                "hook setup (e.g '%s') but no hook '%s' has been provided with the app. "
                                "In order for this app to work with engine %s, you need to provide a "
                                "custom hook implementation. Please contact support for more "
                                "information" % (self, settings_name, default_hook_name, path, engine_name))                
            
        elif hook_expression.startswith("{self}"):
            # bundle local reference
            hooks_folder = os.path.join(self.disk_location, "hooks")
            path = hook_expression.replace("{self}", hooks_folder)
            path = path.replace("/", os.path.sep)
        
        elif hook_expression.startswith("{config}"):
            # config hook 
            hooks_folder = self.tank.pipeline_configuration.get_hooks_location()
            path = hook_expression.replace("{config}", hooks_folder)
            path = path.replace("/", os.path.sep)
        
        elif hook_expression.startswith("{$") and "}" in hook_expression:
            # environment variable: {$HOOK_PATH}/path/to/foo.py
            env_var = re.match("^\{\$([^\}]+)\}", hook_expression).group(1)
            if env_var not in os.environ:
                raise TankError("%s config setting %s: This hook is referring to the configuration value '%s', "
                                "but no environment variable named '%s' can be "
                                "found!" % (self, settings_name, hook_expression, env_var))
            env_var_value = os.environ[env_var]
            path = hook_expression.replace("{$%s}" % env_var, env_var_value)
            path = path.replace("/", os.path.sep)        
        
        elif hook_expression.startswith("{") and "}" in hook_expression:
            # bundle instance (e.g. '{tk-framework-perforce_v1.x.x}/foo/bar.py' )
            # first find the bundle instance
            instance = re.match("^\{([^\}]+)\}", hook_expression).group(1)
            # for now, only look at framework instance names. Later on,
            # if the request ever comes up, we could consider extending
            # to supporting app instances etc. However we would need to
            # have some implicit rules for handling ambiguity since
            # there can be multiple items (engines, apps etc) potentially
            # having the same instance name.
            fw_instances = self.__environment.get_frameworks()
            if instance not in fw_instances:
                raise TankError("%s config setting %s: This hook is referring to the configuration value '%s', "
                                "but no framework with instance name '%s' can be found in the currently "
                                "running environment. The currently loaded frameworks "
                                "are %s." % (self, settings_name, hook_expression, instance, ", ".join(fw_instances)))

            fw_desc = self.__environment.get_framework_descriptor(instance)
            if not(fw_desc.exists_local()):
                raise TankError("%s config setting %s: This hook is referring to the configuration value '%s', "
                                "but the framework with instance name '%s' does not exist on disk. Please run "
                                "the tank cache_apps command." % (self, settings_name, hook_expression, instance))
            
            # get path to framework on disk
            hooks_folder = os.path.join(fw_desc.get_path(), "hooks")
            # create the path to the file
            path = hook_expression.replace("{%s}" % instance, hooks_folder)
            path = path.replace("/", os.path.sep)
            
        else:
            # old school config hook name, e.g. just 'foo'
            hook_folder = self.tank.pipeline_configuration.get_hooks_location()
            path = os.path.join(hook_folder, "%s.py" % hook_expression)            

        return path


    def __execute_hook_internal(self, settings_name, hook_expression, method_name, **kwargs):
        """
        Internal method for executing the specified hook. This method handles
        resolving an environment configuration value into a path on disk.
        
        There are two generations of hook formats - old-style and new-style.
        
        Old style formats:
        
        - hook_setting: foo     -- Resolves 'foo' to CURRENT_PC/hooks/foo.py
        - hook_setting: default -- Resolves the value from the info.yml manifest and uses 
          the default hook code supplied by the bundle.
        
        New style formats:
        
        - hook_setting: {$HOOK_PATH}/path/to/foo.py  -- environment variable.
        - hook_setting: {self}/path/to/foo.py   -- looks in the hooks folder in the local bundle
        - hook_setting: {config}/path/to/foo.py -- looks in the hooks folder in the config
        - hook_setting: {tk-framework-perforce_v1.x.x}/path/to/foo.py -- looks in the hooks folder of a
          framework instance that exists in the current environment. Basically, each entry inside the 
          frameworks section in the current environment can be specified here - all these entries are 
          on the form frameworkname_versionpattern, for example tk-framework-widget_v0.1.2 or 
          tk-framework-shotgunutils_v1.3.x. 
          
        :param settings_name: If this hook is associated with a setting in the bundle, this is the
                              name of that setting. This is used to identify the inheritance relationships
                              between the hook expression that is evaluated and if this hook derives from
                              a hook inside an app. 
        :param hook_expression: The path expression to a hook.
        :param method_name: The method in the hook to execute, or None if the default hook method
                            is supposed to be executed.
        """
        # split up the config value into distinct items
        unresolved_hook_paths = hook_expression.split(":")
        
        # first of all, see if we should add a base class hook to derive from:
        # 
        # Basically, any overridden hook implicitly derives from the default hook.
        # specified in the manifest.
        # if the settings value is not {self} add this to the inheritance chain.
        # Examples:
        #
        # Manifest: {self}/foo_{engine_name}.py
        # In config: {config}/my_custom_hook.py
        # The my_custom_hook.py implicitly derives from the python class defined 
        # in the manifest, so prepend it:
        # hook_paths: ["{self}/foo_tk-maya.py", "{config}/my_custom_hook.py" ]
        #
        # Check only new-style hooks. All new style hooks start with a { 
        if unresolved_hook_paths[0].startswith("{") and not unresolved_hook_paths[0].startswith("{self}"):
            # this is a new style hook that is not the default hook value.
            # now prepend the default hook first in the list 
            manifest = self.__descriptor.get_configuration_schema()
            
            default_value = None
            
            if settings_name:
                default_value = manifest.get(settings_name).get("default_value")
            
            if default_value: # possible not to have a default value!
                
                if constants.TANK_HOOK_ENGINE_REFERENCE_TOKEN in default_value:
                    try:
                        # note - this technically violates the generic nature of the bundle
                        # base class implementation (because the engine member is not defined in bundle
                        # but in App and Framework but NOT in the Engine class) - an engine trying to define
                        # a hook using the {engine_name} construct will therefore get an error.
                        engine_name = self.engine.name
                    except:
                        raise TankError("%s: Failed to find the associated engine "
                                        "when trying to access hook %s" % (self, hook_expression))
                    
                    default_value = default_value.replace(constants.TANK_HOOK_ENGINE_REFERENCE_TOKEN, engine_name)
            
                # expand the default value to be referenced from {self} and with the .py suffix 
                # for backwards compatibility with the old syntax where the default value could
                # just be 'hook_name' with implicit '{self}' and no suffix!
                if not default_value.startswith("{self}"):
                    default_value = "{self}/%s.py" % default_value
                    
                # so now we have a path to a potential default hook inside the app or engine
                # There is however one possibility when there may not be a hook, and this is 
                # when {engine_name} is defined as part of the default value, but no default hook
                # exists for the engine that we are currently running. In this case, we don't want
                # to wedge in this non-existing hook file into the inheritance chain because it does
                # not exist!
                full_path = self.__resolve_hook_path(settings_name, default_value)
                if os.path.exists(full_path):
                    # add to inheritance path
                    unresolved_hook_paths.insert(0, default_value)
        
        # resolve paths into actual file paths
        resolved_hook_paths = [self.__resolve_hook_path(settings_name, x) for x in unresolved_hook_paths]
                
        ret_value = hook.execute_hook_method(resolved_hook_paths, self, method_name, **kwargs)
        
        return ret_value

        

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
            processed_val = self.__tk.execute_core_hook(hook_name, 
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
        if value is None:
            return value
        
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
