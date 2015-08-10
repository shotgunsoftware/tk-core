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
    
    def __init__(self, engine, descriptor, settings, env):
        """
        Called by the app loader framework. The constructor
        is not supposed to be overridden by deriving classes.
        
        :param engine: The engine instance to connect this fw to
        :param app_name: The short name of this framework (e.g. tk-framework-widget)
        :param settings: a settings dictionary for this fw
        :param env: the environment that the framework belongs to
        """

        # init base class
        TankBundle.__init__(self, engine.tank, engine.context, settings, descriptor, env)
        
        self.__engine = engine

        self.log_debug("Framework init: Instantiating %s" % self)
                
    def __repr__(self):        
        return "<Sgtk Framework 0x%08x: %s, engine: %s>" % (id(self), self.name, self.engine)

    def _destroy_framework(self):
        """
        Called by the parent classes when it is time to destroy this framework
        """
        # destroy all our (non-shared) frameworks
        for fw in self.frameworks.values():
            if not fw.is_shared:
                fw._destroy_framework()
        # and destroy self
        self.log_debug("Destroying %s" % self)
        self.destroy_framework()

    ##########################################################################################
    # properties
        
    @property
    def shotgun(self):
        """
        Delegates to the Sgtk API instance's shotgun connection, which is lazily
        created the first time it is requested.
        
        :returns: Shotgun API handle
        """
        # pass on information to the user agent manager which bundle is returning
        # this sg handle. This information will be passed to the web server logs
        # in the shotgun data centre and makes it easy to track which app and engine versions
        # are being used by clients
        try:
            self.tank.shotgun.tk_user_agent_handler.set_current_framework(self.name, 
                                                                          self.version,
                                                                          self.engine.name,
                                                                          self.engine.version)
        except AttributeError:
            # looks like this sg instance for some reason does not have a
            # tk user agent handler associated.
            pass
        
        return self.tank.shotgun        
        
    @property
    def engine(self):
        """
        The engine that this framework is connected to
        """
        return self.__engine                

    @property
    def is_shared(self):
        """
        Boolean indicating whether this is a shared framework.
        """
        return self.descriptor.is_shared_framework()
        
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
        
        # try to get a shared instance for this framework
        fw_obj = engine_obj._get_shared_framework(fw_inst_name)

        if fw_obj is None:
            # load framework
            # this only occurs once per instance name for shared frameworks
            fw_obj = load_framework(engine_obj, env, fw_inst_name)

            if fw_obj.is_shared:
                # register this framework for reuse by other bundles
                engine_obj._register_shared_framework(fw_inst_name, fw_obj)
        
        # note! frameworks are keyed by their code name, not their instance name
        parent_obj.frameworks[fw_obj.name] = fw_obj
        
        


def load_framework(engine_obj, env, fw_instance_name):
    """
    Validates, loads and initializes a framework.  If the framework is available from the list of 
    shared frameworks maintained by the engine then the shared framework is returned, otherwise a 
    new instance of the framework will be returned.

    :param engine_obj:          The engine instance to use when loading the framework
    :param env:                 The environment containing the framework instance to load
    :param fw_instance_name:    The instance name of the framework (e.g. tk-framework-foo_v0.x.x)
    :returns:                   An initialized framework object.
    :raises:                    TankError if the framework can't be found, has an invalid
                                configuration or fails to initialize.
    """
    # see if we have a shared instance of the framework:
    fw = engine_obj._get_shared_framework(fw_instance_name)
    if fw:
        # win!
        return fw

    # get the framework descriptor
    descriptor = env.get_framework_descriptor(fw_instance_name)
    if not descriptor.exists_local():
        raise TankError("Cannot load Framework! %s does not exist on disk." % descriptor)

    # Load the settings for the framework and validate them
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

    except Exception:
        # code execution error in the validation. 
        raise TankError("Could not validate framework %s: %s" % (fw_instance_name, e))

    # load the framework
    try:
        # initialize fw class
        fw = _create_framework_instance(engine_obj, descriptor, fw_settings, env)

        # load any frameworks required by the framework :)
        setup_frameworks(engine_obj, fw, env, descriptor)

        # and run the init
        fw.init_framework()

        # if it's a shared framework then add it to the engine so we can re-use it
        # again in the future if needed:
        if fw.is_shared:
            # register this framework for reuse by other bundles
            engine_obj._register_shared_framework(fw_instance_name, fw)

    except Exception, e:
        raise TankError("Framework %s failed to initialize: %s" % (descriptor, e))

    return fw


def _create_framework_instance(engine, descriptor, settings, env):
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
    obj = class_obj(engine, descriptor, settings, env)
    return obj
