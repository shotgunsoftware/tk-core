"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Defines the base class for all Tank Apps.

"""

import os
import sys

from .. import loader
from . import constants 

from ..errors import TankError
from .bundle import TankBundle

class Application(TankBundle):
    """
    Base class for an app in Tank.
    """
    
    def __init__(self, engine, descriptor, settings, instance_name):
        """
        Called by the app loader framework. The constructor
        is not supposed to be overridden by deriving classes.
        
        :param engine: The engine instance to connect this app to
        :param app_name: The short name of this app (e.g. tk-nukepublish)
        :param settings: a settings dictionary for this app
        """

        # init base class
        TankBundle.__init__(self, engine.tank, engine.context, settings, descriptor)
        
        self.__engine = engine
        self.__instance_name = instance_name

        self.log_debug("App init: Instantiating %s" % self)
                
        # now if a folder named python is defined in the app, add it to the pythonpath
        app_path = os.path.dirname(sys.modules[self.__module__].__file__)
        python_path = os.path.join(app_path, constants.BUNDLE_PYTHON_FOLDER)
        if os.path.exists(python_path):
            # only append to python path if __init__.py does not exist
            # if __init__ exists, we should use the special tank import instead
            init_path = os.path.join(python_path, "__init__.py")
            if not os.path.exists(init_path):
                self.log_debug("Appending to PYTHONPATH: %s" % python_path)
                sys.path.append(python_path)

    def __repr__(self):        
        return "<Sgtk App 0x%08x: %s, engine: %s>" % (id(self), self.name, self.engine)

    def _destroy_frameworks(self):
        """
        Called on destroy, prior to calling destroy_app
        """
        for fw in self.frameworks.values():
            fw._destroy_framework()        

    ##########################################################################################
    # properties
        
    @property
    def instance_name(self):
        """
        The name for this app instance
        """
        return self.__instance_name
        
    @property
    def engine(self):
        """
        The engine that this app is connected to
        """
        return self.__engine                
        
    ##########################################################################################
    # init and destroy
        
    def init_app(self):
        """
        Implemented by deriving classes in order to initialize the app
        Called by the engine as it loads the app.
        """
        pass

    def destroy_app(self):
        """
        Implemented by deriving classes in order to tear down the app
        Called by the engine as it is being destroyed.
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


def get_application(engine, app_folder, descriptor, settings, instance_name):
    """
    Internal helper method. 
    (Removed from the engine base class to make it easier to run unit tests).
    Returns an application object given an engine and app settings.
    
    :param engine: the engine this app should run in
    :param app_folder: the folder on disk where the app is located
    :param descriptor: descriptor for the app
    :param settings: a settings dict to pass to the app
    """
    plugin_file = os.path.join(app_folder, constants.APP_FILE)
        
    # Instantiate the app
    class_obj = loader.load_plugin(plugin_file, Application)
    obj = class_obj(engine, descriptor, settings, instance_name)
    return obj

