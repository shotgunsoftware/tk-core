"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Methods for handling of the tank command

"""

from ...errors import TankError
from .. import env_admin
from .action_base import Action



class InstallAppAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "install_app", 
                        Action.PC_LOCAL, 
                        "Adds a new app to your tank configuration.", 
                        "Configuration")
    
    def run(self, log, args):

        if len(args) != 3:
            
            log.info("Please specify an app to install and an environment to install it into!")
            log.info("The following environments exist in the current configuration: ")
            for e in self.tk.pipeline_configuration.get_environments():
                log.info(" - %s" % e)            
            log.info("")
            log.info("Syntax:  install_app environment_name engine_name app_name")
            log.info("Example: install_app asset tk-shell tk-multi-about")
            raise TankError("Invalid number of parameters.")

        env_name = args[0]
        engine_name = args[1]
        app_name = args[2]
        env_admin.install_app(log, self.tk, env_name, engine_name, app_name)


class InstallEngineAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "install_engine", 
                        Action.PC_LOCAL, 
                        "Adds a new engine to your tank configuration.", 
                        "Configuration")
    
    def run(self, log, args):

        if len(args) != 2:
            log.info("Please specify an engine to install and an environment to install it into!")
            log.info("The following environments exist in the current configuration: ")
            for e in self.tk.pipeline_configuration.get_environments():
                log.info(" - %s" % e)            
            log.info("")
            log.info("Syntax:  install_engine environment_name engine_name")
            log.info("Example: install_engine asset tk-shell")
            raise TankError("Invalid number of parameters.")
                    
        env_name = args[0]
        engine_name = args[1]   
        env_admin.install_engine(log, self.tk, env_name, engine_name)



class AppUpdatesAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "updates", 
                        Action.PC_LOCAL, 
                        "Checks if there are any app or engine updates for the current configuration.", 
                        "Configuration")
    
    def run(self, log, args):
        if len(args) != 0:
            raise TankError("Invalid arguments! Run with --help for more details.")
        env_admin.check_for_updates(log, self.tk)

