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

class Framework(TankBundle):
    """
    Base class for an app in Tank.
    """
    
    def __init__(self, engine, descriptor, settings):
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

        self.log_debug("Framework init: Instantiating %s" % self)
                
    def __repr__(self):        
        return "<Tank Framework 0x%08x: %s, engine: %s>" % (id(self), self.name, self.engine)

    ##########################################################################################
    # properties
        
    @property
    def engine(self):
        """
        The engine that this app is connected to
        """
        return self.__engine                
        
    ##########################################################################################
    # init and destroy
        
    def init_framework(self):
        """
        Implemented by deriving classes in order to initialize the framework
        Called by the engine as it loads the app.
        """
        pass

    def destroy_framework(self):
        """
        Implemented by deriving classes in order to tear down the framework
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


