"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Defines the base class for all Tank Frameworks.

"""

import os
import sys

from .. import loader
from . import constants 

from ..errors import TankError
from .bundle import TankBundle
from . import validation

# global variable that holds a stack of references to
# a current bundle object - this variable is populated
# whenever the bundle.import_module method is executed
# and is a way for import_framework() to be able to resolve
# the current bundle even when being recursively called 
# inside an import_module call
CURRENT_BUNDLE_DOING_IMPORT = []


class Framework(TankBundle):
    """
    Base class for an app in Tank.
    """
    
    def __init__(self, engine, descriptor, settings):
        """
        Called by the app loader framework. The constructor
        is not supposed to be overridden by deriving classes.
        
        :param engine: The engine instance to connect this fw to
        :param app_name: The short name of this framework (e.g. tk-framework-widget)
        :param settings: a settings dictionary for this fw
        """

        # init base class
        TankBundle.__init__(self, engine.tank, engine.context, settings, descriptor)
        
        self.__engine = engine

        self.log_debug("Framework init: Instantiating %s" % self)
                
    def __repr__(self):        
        return "<Tank Framework 0x%08x: %s, engine: %s>" % (id(self), self.name, self.engine)

    def _destroy_framework(self):
        """
        Called by the parent classes when it is time to destroy this framework
        """
        # destroy all our frameworks
        for fw in self.frameworks.values():
            fw._destroy_framework() 
        # and destroy self
        self.log_debug("Destroying %s" % self)
        self.destroy_framework()

    ##########################################################################################
    # properties
        
    @property
    def engine(self):
        """
        The engine that this framework is connected to
        """
        return self.__engine                
        
    ##########################################################################################
    # init and destroy
        
    def init_framework(self):
        """
        Implemented by deriving classes in order to initialize the framework
        """
        pass

    def destroy_framework(self):
        """
        Implemented by deriving classes in order to tear down the framework
        """
        pass
    
    
    ##########################################################################################
    # logging methods, delegated to the current engine

    def log_debug(self, msg):
        self.engine.log_debug(msg)

    def log_info(self, msg):
        self.engine.log_info(msg)

    def log_warning(self, msg):
        self.engine.log_warning(msg)

    def log_error(self, msg):
        self.engine.log_error(msg)

    def log_exception(self, msg):
        self.engine.log_exception(msg)



###################################################################################################
#
# Helper methods for loading frameworks
#

def setup_frameworks(engine_obj, parent_obj, env, parent_descriptor):
    """
    Checks if any frameworks are needed for the current item
    and in that case loads them - recursively
    """
    
    # look into the environment, get descriptors for all frameworks that our item needs:
    framework_instance_names = validation.validate_and_return_frameworks(parent_descriptor, env)
    
    # looks like all of the frameworks are valid! Load them one by one
    for fw_inst_name in framework_instance_names:
        
        engine_obj.log_debug("%s - loading framework %s" % (parent_obj, fw_inst_name))
        
        fw_obj = load_framework(engine_obj, env, fw_inst_name)
        
        # note! frameworks are keyed by their code name, not their instance name
        parent_obj.frameworks[fw_obj.name] = fw_obj
        
        


def load_framework(engine_obj, env, fw_instance_name):
    """
    Validates, loads and initializes a framework.
    Returns an initialized framework object.
    """
    
    # now get the app location and resolve it into a version object
    descriptor = env.get_framework_descriptor(fw_instance_name)
    if not descriptor.exists_local():
        raise TankError("Cannot load Framework! %s does not exist on disk." % descriptor)
    
    # Load settings for app - skip over the ones that don't validate
    try:

        # check that the context contains all the info that the app needs
        validation.validate_context(descriptor, engine_obj.context)
        
        # make sure the current operating system platform is supported
        validation.validate_platform(descriptor)        
        
        # get the app settings data and validate it.
        fw_schema = descriptor.get_configuration_schema()
                
        fw_settings = env.get_framework_settings(fw_instance_name)
        validation.validate_settings(fw_instance_name, 
                                     engine_obj.tank, 
                                     engine_obj.context, 
                                     fw_schema, 
                                     fw_settings)
                            
    except TankError, e:
        # validation error - probably some issue with the settings!
        raise TankError("Framework configuration Error for %s: %s" % (fw_instance_name, e))
    
    except Exception, e:
        # code execution error in the validation. 
        engine_obj.log_exception("A general exception was caught while trying to " 
                                 "validate the configuration for Framework %s: %s" % (fw_instance_name, e))
        
        raise TankError("Could not validate framework %s: %s" % (fw_instance_name, e))
    
    
    # load the framework
    try:
        # initialize fw class
        fw = _create_framework_instance(engine_obj, descriptor, fw_settings)
        
        # load any frameworks required by the framework :)
        setup_frameworks(engine_obj, fw, env, descriptor)
        
        # and run the init
        fw.init_framework()
        
    except Exception, e:
        raise TankError("Framework %s failed to initialize: %s" % (descriptor, e))
    
    return fw


def _create_framework_instance(engine, descriptor, settings):
    """
    Internal helper method. 
    Returns an framework object given an engine and fw settings.
    
    :param engine: the engine this app should run in
    :param descriptor: descriptor for the fw
    :param settings: a settings dict to pass to the fw
    """
    fw_folder = descriptor.get_path()
    plugin_file = os.path.join(fw_folder, constants.FRAMEWORK_FILE)
        
    # Instantiate the app
    class_obj = loader.load_plugin(plugin_file, Framework)
    obj = class_obj(engine, descriptor, settings)
    return obj
