# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

from .action_base import Action


class AppInfoAction(Action):
    """
    Action that gives a breakdown of all engines and apps in an environment
    """
    
    def __init__(self):
        Action.__init__(self, 
                        "app_info", 
                        Action.PC_LOCAL, 
                        "Shows a breakdown of your installed apps.", 
                        "Developer")
    
    def run(self, log, args):

        log.info("This command lists details about Apps and Engines.")
        log.info("--------------------------------------------------")
        log.info("")
        log.info("Your current configuration is located here:")
        log.info(self.tk.pipeline_configuration.get_path())
        log.info("")

        if len(args) != 1:
            
            log.info("Apps in Toolkit are organized in different environments. "
                     "Environments are loaded depending on which Task is being "
                     "worked on. Each environment then contains a number of engines, which "
                     "are loaded in depending on the application which is being executed. "
                     "Each engine contains a collection of apps which are the tools that will "
                     "appear on the Shotgun menu.")
            log.info("")
            log.info("Use the syntax 'tank app_info environment_name' to view the engines and "
                     "apps for an environment. The following environments are available:")
            log.info("")
            for env_name in self.tk.pipeline_configuration.get_environments():
                log.info(" - %s" % env_name)            
            log.info("")
            return
        
        else:
            
            env_name = args[0]
            log.info("Showing engines and apps for environment '%s'." % env_name)
        
        
        log.info("Below is a listing of all the apps in your current configuration:")
        

        env = self.tk.pipeline_configuration.get_environment(env_name)
        log.info("")
        log.info("")
        log.info("=" * 70)
        log.info("Environment: %s" % env.name)
        log.info("Location:    %s" % env.disk_location)
        log.info("Description: %s" % env.description)
        
        log.info("=" * 70)
        for eng in env.get_engines():
            log.info("")
            log.info("-" * 70)
            log.info("Engine %s" % eng)
            log.info("-" * 70)
            log.info("")
            for app in env.get_apps(eng):
                descriptor = env.get_app_descriptor(eng, app)
                log.info("App %s" % app)
                log.info("-" * (4+len(app)))
                for (k,v) in descriptor.get_location().items():
                    log.info(" %s: %s" % (k.capitalize(), v) )
                log.info(" Docs: %s" % descriptor.get_doc_url())
                log.info("")
        
        log.info("")
        log.info("")
        log.info("- To install a new app, use the command tank install_app")
        log.info("- To switch an app location, use the command tank switch")
        log.info("")

