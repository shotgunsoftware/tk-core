"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Defines the base class for all Tank Engines.

"""

import os
import sys
import traceback

from .. import loader
from .. import hook
from ..errors import TankError, TankEngineInitError
from ..deploy import descriptor

from . import application
from . import constants
from .environment import Environment
from .validation import validate_settings

class Engine(object):
    """
    Base class for an engine in Tank.
    """

    def __init__(self, tk, context, engine_instance_name, env):
        """
        Constructor. Takes the following parameters:
        
        :param tk: Tank API handle
        :param context: A context object to define the context on disk where the engine is operating
        :param engine_instance_name: The name of the engine as it has been defined in the environment.
        :param env: An Environment object to associate with this engine
        """
        self.__tk = tk
        self.__context = context
        self.__env = env
        self.__engine_instance_name = engine_instance_name
        self.__applications = {}
        self.__commands = {}
        self.__sg = None
        self.__currently_initializing_app = None

        # get the descriptor representing the engine        
        self.__descriptor = self.__env.get_engine_descriptor(self.__engine_instance_name)        
        
        # now if a folder named python is defined in the engine, add it to the pythonpath
        my_path = os.path.dirname(sys.modules[self.__module__].__file__)
        python_path = os.path.join(my_path, constants.BUNDLE_PYTHON_FOLDER)
        if os.path.exists(python_path):
            sys.path.append(python_path)
        
        # Get the settings for the engine and then validate them
        self.__settings = self.__env.get_engine_settings(self.__engine_instance_name)
        metadata = self.__env.get_engine_metadata(self.__engine_instance_name)
        schema = metadata["configuration"]
        validate_settings(self.__engine_instance_name, self.__tk, self.__context, schema, self.__settings)
        
        # run the engine init
        self.log_debug("Engine init: Instantiating %s" % self)
        self.log_debug("Engine init: Current Context: %s" % context)

        self.init_engine()
        
        # now load all apps and their settings
        self._load_apps()
        
        # now run the post app init
        self.post_app_init()
        
        
        self.log_debug("Init complete: %s" % self)
        
        
        
        
    def __repr__(self):
        return "<Tank Engine 0x%08x: %s, env: %s>" % (id(self),  
                                                           self.name, 
                                                           self.__env.name)

    ##########################################################################################
    # properties

    @property
    def environment(self):
        """
        A dictionary with information about the environment.
        Returns keys name, description and disk_location.
         
        :returns: dictionary
        """
        data = {}
        data["name"] = self.__env.name
        data["description"] = self.__env.description
        data["disk_location"] = self.__env.disk_location
        
        return data

    @property
    def name(self):
        """
        The short name of the engine (e.g. tk-maya)
        
        :returns: engine name as string
        """
        return self.__descriptor.get_short_name()
    
    @property
    def display_name(self):
        """
        The displayname of the engine (e.g. Maya Engine)
        
        :returns: engine display name as string
        """
        return self.__descriptor.get_display_name()

    @property
    def description(self):
        """
        A short description of the app
        
        :returns: string
        """
        return self.__descriptor.get_description()

    @property
    def version(self):
        """
        The version of the engine (e.g. v0.2.3)
        
        :returns: string representing the version
        """
        return self.__descriptor.get_version()

    @property
    def instance_name(self):
        """
        The instance name for this engine. The instance name
        is the entry that is defined in the environment file.
        
        :returns: instance name as string
        """
        return self.__engine_instance_name

    @property
    def disk_location(self):
        """
        The folder on disk where this engine is located
        """
        path_to_this_file = os.path.abspath(sys.modules[self.__module__].__file__)
        return os.path.dirname(path_to_this_file)

    @property
    def context(self):
        """
        The current context associated with this engine
        
        :returns: context object
        """
        return self.__context

    @property
    def apps(self):
        """
        Dictionary of apps associated with this engine
        
        :returns: dictionary with keys being app name and values being app objects
        """
        return self.__applications
    
    @property
    def shotgun(self):
        """
        Delegates to the Tank API instance's shotgun connection, which is lazily
        created the first time it is requested.
        
        :returns: Shotgun API handle
        """
        return self.__tk.shotgun
    
    @property
    def tank(self):
        """
        Returns a Tank API instance associated with this engine
        
        :returns: Tank API handle 
        """
        return self.__tk
    
    @property
    def commands(self):
        """
        Returns a dictionary representing all the commands that have been registered
        by apps in this engine. Each dictionary item contains the following keys:
        
        * callback - function pointer to function to execute for this command
        * properties - dictionary with free form options - these are typically
          engine specific and driven by convention.
        
        :returns: commands dictionary, keyed by command name
        """
        return self.__commands
    
    @property
    def documentation_url(self):
        """
        Return the relevant documentation url for this engine.
        
        :returns: url string, None if no documentation was found
        """
        return self.__descriptor.get_doc_url()        

    ##########################################################################################
    # init and destroy
    
    def init_engine(self):
        """
        Sets up the engine into an operational state.
        
        Implemented by deriving classes.
        """
        pass
    
    def post_app_init(self):
        """
        Runs after all apps have been initialized.
        
        Implemented by deriving classes.
        """
        pass
    
    def destroy(self):
        """
        Destroy all apps, then call destroy_engine so subclasses can add their own tear down code.
        
        This method should not be subclassed.
        """
        self._destroy_apps()
        self.destroy_engine()
        
        # finally remove the current engine reference
        set_current_engine(None)
    
    def destroy_engine(self):
        """
        Called when the engine should tear down itself and all its apps.
        Implemented by deriving classes.
        """
        pass
    
    ##########################################################################################
    # public methods

    def register_command(self, name, callback, properties=None):
        """
        Register a command with a name and a callback function. Properties can store
        implementation specific configuration, like if a tooltip is supported.
        Typically called from the init_app() method of an app.
        """
        if properties is None:
            properties = {}
        if self.__currently_initializing_app is not None:
            # track which apps this request came from
            properties["app"] = self.__currently_initializing_app
        self.__commands[name] = { "callback": callback, "properties": properties }
        
    def get_setting(self, key, default=None):
        """
        Get a value from the engine's settings

        :param key: config name
        :param default: default value to return
        """
        return self.__settings.get(key, default)
            
    def execute_hook(self, key, **kwargs):
        """
        Shortcut for grabbing the hook name used in the settings, then calling execute_hook_by_name() on it.
        """
        hook_name = self.get_setting(key)
        return self.execute_hook_by_name(hook_name, **kwargs)

    def execute_hook_by_name(self, hook_name, **kwargs):
        """
        Executes the named engine level hook. 
        The parent parameter passed to the hook will be the current engine.
        """
        hook_folder = constants.get_hooks_folder(self.tank.project_path)
        hook_path = os.path.join(hook_folder, "%s.py" % hook_name)
        return hook.execute_hook(hook_path, self, **kwargs)
    
    ##########################################################################################
    # simple batch queue
    
    def add_to_queue(self, name, method, args):
        raise NotImplementedError("Queue not implemented by this engine!")
    
    def report_progress(self, percent):
        raise NotImplementedError("Queue not implemented by this engine!")
    
    def execute_queue(self):
        raise NotImplementedError("Queue not implemented by this engine!")
    
    ##########################################################################################
    # logging interfaces

    def log_debug(self, msg):
        """
        Debug logging.
        Implemented in deriving class.
        """
        pass
    
    def log_info(self, msg):
        """
        Info logging.
        Implemented in deriving class.
        """
        pass
        
    def log_warning(self, msg):
        """
        Warning logging.
        Implemented in deriving class.
        """
        pass
    
    def log_error(self, msg):
        """
        Debug logging.
        Implemented in deriving class - however we provide a basic implementation here.
        """        
        # fall back to std out error reporting if deriving class does not implement this.
        sys.stderr("Error: %s\n" % msg)
    
    def log_exception(self, msg):
        """
        Helper method. Typically not overridden by deriving classes.
        This method is called inside an except clause and it creates an formatted error message
        which is logged as an error.
        """
        (exc_type, exc_value, exc_traceback) = sys.exc_info()
        message = ""
        message += "\n\n"
        message += "Message: %s\n" % msg
        message += "Environment: %s\n" % self.__env.name
        message += "Exception: %s - %s\n" % (exc_type, exc_value)
        message += "Traceback (most recent call last):\n"
        message += "".join( traceback.format_tb(exc_traceback))
        message += "\n\n"
        self.log_error(message)
        
    ##########################################################################################
    # private and protected methods
    
    def _load_apps(self):
        """
        Populate the __applications dictionary, skip over apps that fail to initialize.
        """
        for app_instance_name in self.__env.get_apps(self.__engine_instance_name):
            
            # Load settings for app - skip over the ones that don't validate
            try:
                # get the app settings data and validate it.
                app_metadata = self.__env.get_app_metadata(self.__engine_instance_name, app_instance_name)
                app_schema = app_metadata["configuration"]
                app_settings = self.__env.get_app_settings(self.__engine_instance_name, app_instance_name)
                validate_settings(app_instance_name, self.__tk, self.__context, app_schema, app_settings)
                # for multi engine apps, make sure our engine is supported
                supported_engines = app_metadata.get("supported_engines")
                if supported_engines and self.name not in supported_engines:
                    self.log_error("The app %s could not be loaded since it only supports "
                                   "the following engines: %s" % (app_instance_name, supported_engines))
                    continue
                    
            except TankError as e:
                # validation error - probably some issue with the settings!
                # report this as an error message.
                self.log_error("App configuration Error for %s. It will not "
                               "be loaded. \n\nDetails: %s" % (app_instance_name, e))
                continue
            
            except Exception as e:
                # code execution error in the validation. Report this as an error 
                # with the engire call stack!
                self.log_exception("A general exception was caught while trying to" 
                                   "validate the configuration for app %s. "
                                   "The app will not be loaded.\n%s" % (app_instance_name, e))
                continue
            
            # now get the app location and resolve it into a version object
            descriptor = self.__env.get_app_descriptor(self.__engine_instance_name, app_instance_name)
            if not descriptor.exists_local():
                self.log_error("Cannot start app! %s does not exist on disk." % descriptor)
            
            app_dir = descriptor.get_path()
                                    
            # load the app
            try:
                app = application.get_application(self, app_dir, descriptor, app_settings)
                # track the init of the app
                self.__currently_initializing_app = app
                try:
                    app.init_app()
                finally:
                    self.__currently_initializing_app = None
            except Exception as e:
                self.log_exception("App %s failed to initialize - "
                                   "it will not be loaded:\n%s" % (app_dir, e))
            else:
                # note! Apps are keyed by their instance name, meaning that we 
                # could theoretically have multiple instances of the same app.
                self.__applications[app_instance_name] = app

    def _destroy_apps(self):
        """
        Call the destroy_app method on all loaded apps
        """
        
        for app in self.__applications.values():
            app.destroy_app()


##########################################################################################
# Engine management

g_current_engine = None

def set_current_engine(eng):
    """
    Sets the current engine
    """
    global g_current_engine
    g_current_engine = eng

def current_engine():
    """
    Returns the current engine
    """
    global g_current_engine
    return g_current_engine
        
def start_engine(engine_name, tk, context):
    """
    Creates an engine and makes it the current engine.
    Returns the newly created engine object.
    
    Raises TankEngineInitError if an engine could not be started 
    for the passed context.    
    """
    # first ensure that an engine is not currently running
    if current_engine():
        raise TankError("An engine (%s) is already running! Before you can start a new engine, "
                        "please shut down the previous one using the command " 
                        "tank.platform.current_engine().destroy()." % current_engine())
    
    # get the environment via the pick_environment hook
    env_name = __pick_environment(engine_name, tk, context)
    
    # get the path to the environment file given its name
    env_path = constants.get_environment_path(env_name, tk.project_path)
    
    # now we can instantiate a wrapper class around the data
    # this will load it and check basic things.
    env = Environment(env_path)
    
    # make sure that the environment has an engine instance with that name
    if not engine_name in env.get_engines():
        raise TankEngineInitError("Cannot find an engine instance %s in %s." % (engine_name, env))
    
    # get the location for our engine    
    engine_descriptor = env.get_engine_descriptor(engine_name)
    
    # make sure it exists locally
    if not engine_descriptor.exists_local():
        raise TankEngineInitError("Cannot start engine! %s does not exist on disk" % engine_descriptor)
    
    # get path to engine code
    engine_path = engine_descriptor.get_path()
    plugin_file = os.path.join(engine_path, constants.ENGINE_FILE)
    
    # Instantiate the engine
    class_obj = loader.load_plugin(plugin_file, Engine)
    obj = class_obj(tk, context, engine_name, env)
    
    # register this engine as the current engine
    set_current_engine(obj)
    
    return obj

##########################################################################################
# utilities

def __pick_environment(engine_name, tk, context):
    """
    Call out to the pick_environment core hook to determine which environment we should load
    based on the current context. The Shotgun engine provides its own implementation.
    """

    # for now, handle shotgun as a special case!
    # if the engine_name is shotgun, then return shotgun as the environment
    if engine_name in constants.SHOTGUN_ENGINES:
        return constants.SHOTGUN_ENVIRONMENT

    try:
        env_name = tk.execute_hook(constants.PICK_ENVIRONMENT_CORE_HOOK_NAME, context=context)
    except Exception, e:
        raise TankEngineInitError("Engine %s cannot initialize - the pick environment hook "
                                 "reported the following error: %s" % (engine_name, e))

    if env_name is None:
        # the pick_environment hook could not determine an environment
        # this may be because an incomplete Context was passed.
        # without an environment, engine creation cannot succeed.
        # raise an exception with a message
        raise TankEngineInitError("Engine %s cannot initialize - the pick environment hook was not "
                                  "able to return an environment to use, given the context %s. "
                                  "Usually this is because the context contains insufficient information "
                                  "for an environment to be determined." % (engine_name, context))

    return env_name

