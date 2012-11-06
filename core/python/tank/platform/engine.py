"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Defines the base class for all Tank Engines.

"""

import os
import sys
import traceback

from .. import loader
from ..errors import TankError, TankEngineInitError
from ..deploy import descriptor

from . import application
from . import constants
from .environment import Environment
from .validation import validate_settings
from .bundle import TankBundle
from .framework import setup_frameworks

class Engine(TankBundle):
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
        
        self.__env = env
        self.__engine_instance_name = engine_instance_name
        self.__applications = {}
        self.__commands = {}
        self.__currently_initializing_app = None
        
        # get the engine settings
        settings = self.__env.get_engine_settings(self.__engine_instance_name)
        
        # get the descriptor representing the engine        
        descriptor = self.__env.get_engine_descriptor(self.__engine_instance_name)        
        
        # init base class
        TankBundle.__init__(self, tk, context, settings, descriptor)

        # Get the settings for the engine and then validate them
        metadata = self.__env.get_engine_metadata(self.__engine_instance_name)
        engine_schema = metadata["configuration"]
        engine_frameworks = metadata.get("frameworks")
        validate_settings(self.__engine_instance_name, tk, context, engine_schema, settings)
        
        # set up any frameworks defined
        setup_frameworks(self, self, metadata, self.__env, descriptor)
        
        # run the engine init
        self.log_debug("Engine init: Instantiating %s" % self)
        self.log_debug("Engine init: Current Context: %s" % context)

        # now if a folder named python is defined in the engine, add it to the pythonpath
        my_path = os.path.dirname(sys.modules[self.__module__].__file__)
        python_path = os.path.join(my_path, constants.BUNDLE_PYTHON_FOLDER)
        if os.path.exists(python_path):            
            # only append to python path if __init__.py does not exist
            # if __init__ exists, we should use the special tank import instead
            init_path = os.path.join(python_path, "__init__.py")
            if not os.path.exists(init_path):
                self.log_debug("Appending to PYTHONPATH: %s" % python_path)
                sys.path.append(python_path)

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
    def instance_name(self):
        """
        The instance name for this engine. The instance name
        is the entry that is defined in the environment file.
        
        :returns: instance name as string
        """
        return self.__engine_instance_name

    @property
    def apps(self):
        """
        Dictionary of apps associated with this engine
        
        :returns: dictionary with keys being app name and values being app objects
        """
        return self.__applications
    
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
        for fw in self.frameworks.values():
            fw._destroy_framework()

        self._destroy_apps()
        
        self.log_debug("Destroying %s" % self)
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
        
        if exc_traceback is None:
            # we are not inside an exception handler right now.
            # someone is calling log_exception from the running code.
            # in this case, present the current stack frame
            # and a sensible message
            stack_frame = traceback.extract_stack()
            traceback_str = "".join(traceback.format_list(stack_frame))
            exc_type = "OK"
            exc_value = "No current exception."
        
        else:    
            traceback_str = "".join( traceback.format_tb(exc_traceback))
        
        message = ""
        message += "\n\n"
        message += "Message: %s\n" % msg
        message += "Environment: %s\n" % self.__env.name
        message += "Exception: %s - %s\n" % (exc_type, exc_value)
        message += "Traceback (most recent call last):\n"
        message += traceback_str
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
                validate_settings(app_instance_name, self.tank, self.context, app_schema, app_settings)
                                
                # for multi engine apps, make sure our engine is supported
                supported_engines = app_metadata.get("supported_engines")
                if supported_engines and self.name not in supported_engines:
                    self.log_error("The app %s could not be loaded since it only supports "
                                   "the following engines: %s" % (app_instance_name, supported_engines))
                    continue
                    
            except TankError, e:
                # validation error - probably some issue with the settings!
                # report this as an error message.
                self.log_error("App configuration Error for %s. It will not "
                               "be loaded. \n\nDetails: %s" % (app_instance_name, e))
                continue
            
            except Exception, e:
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
                # create the object, run the constructor
                app = application.get_application(self, app_dir, descriptor, app_settings)
                
                # load any frameworks required
                setup_frameworks(self, app, app_metadata, self.__env, descriptor)
                
                # track the init of the app
                self.__currently_initializing_app = app
                try:
                    app.init_app()
                finally:
                    self.__currently_initializing_app = None
            except Exception, e:
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
            app._destroy_frameworks()
            self.log_debug("Destroying %s" % app)
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

