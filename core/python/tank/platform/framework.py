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
from .validation import validate_settings, validate_frameworks

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

def setup_frameworks(engine_obj, parent_obj, parent_metadata, env, parent_descriptor):
    """
    Checks if any frameworks are needed for the current item
    and in that case loads them - recursively
    """
    
    item_frameworks = parent_metadata.get("frameworks")
    
    framework_instance_names = validate_frameworks(parent_obj.name, env, item_frameworks)
    
    # looks like all of the frameworks are valid! Load them one by one
    for fw_inst_name in framework_instance_names:
        _load_framework(engine_obj, env, parent_obj, fw_inst_name)


def _load_framework(engine_obj, env, parent_obj, fw_instance_name):
    """
    Validates, loads and initializes a framework and attaches it to a parent object.
    """
    engine_obj.log_debug("%s - loading framework %s" % (parent_obj, fw_instance_name))
    
    # Load settings for app - skip over the ones that don't validate
    try:
        
        # get the app settings data and validate it.
        fw_metadata = env.get_framework_metadata(fw_instance_name)
        fw_schema = fw_metadata["configuration"]
        
        fw_settings = env.get_framework_settings(fw_instance_name)
        validate_settings(fw_instance_name, 
                          engine_obj.tank, 
                          engine_obj.context, 
                          fw_schema, 
                          fw_settings)
                            
    except TankError as e:
        # validation error - probably some issue with the settings!
        raise TankError("Framework configuration Error for %s: %s" % (fw_instance_name, e))
    
    except Exception as e:
        # code execution error in the validation. 
        parent_obj.log_exception("A general exception was caught while trying to " 
                                 "validate the configuration for Framework %s: %s" % (fw_instance_name, e))
        
        raise TankError("Could not validate framework %s: %s" % (fw_instance_name, e))
    
    # now get the app location and resolve it into a version object
    descriptor = env.get_framework_descriptor(fw_instance_name)
    if not descriptor.exists_local():
        raise TankError("Cannot load Framework! %s does not exist on disk." % descriptor)
    
    fw_dir = descriptor.get_path()
                            
    # load the framework
    try:
        # initialize fw class
        fw = get_framework(engine_obj, fw_dir, descriptor, fw_settings)
        
        # load any frameworks required by the framework :)
        setup_frameworks(engine_obj, fw, fw_metadata, env, descriptor)
        
        # and run the init
        fw.init_framework()
        
    except Exception as e:
        raise TankError("Framework %s failed to initialize: %s" % (fw_dir, e))
    
    else:
        # note! frameworks are keyed by their code name, not their instance name
        parent_obj.frameworks[descriptor.get_short_name()] = fw


def get_framework(engine, fw_folder, descriptor, settings):
    """
    Internal helper method. 
    Returns an framework object given an engine and fw settings.
    
    :param engine: the engine this app should run in
    :param fw_folder: the folder on disk where the fw is located
    :param descriptor: descriptor for the fw
    :param settings: a settings dict to pass to the fw
    """
    plugin_file = os.path.join(fw_folder, constants.FRAMEWORK_FILE)
        
    # Instantiate the app
    class_obj = loader.load_plugin(plugin_file, Framework)
    obj = class_obj(engine, descriptor, settings)
    return obj
