# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
from .action_base import Action
from ...errors import TankError
from ...platform import validation


class ValidateConfigAction(Action):
    """
    Action that looks at the config and validates all parameters
    """    
    def __init__(self):
        Action.__init__(self, 
                        "validate", 
                        Action.TK_INSTANCE, 
                        ("Validates your current Configuration to check that all "
                        "environments have been correctly configured."), 
                        "Configuration")
        
        # this method can be executed via the API
        self.supports_api = True
        
    def run_noninteractive(self, log, parameters):
        """
        API accessor
        """
        return self._run(log)
    
    def run_interactive(self, log, args):
        """
        Tank command accessor
        """
        if len(args) != 0:
            raise TankError("This command takes no arguments!")
        return self._run(log)
        
    def _run(self, log):
        """
        Actual execution payload
        """ 
        
        log.info("")
        log.info("")
        log.info("Welcome to the Shotgun Pipeline Toolkit Configuration validator!")
        log.info("")
    
        try:
            envs = self.tk.pipeline_configuration.get_environments()
        except Exception, e:
            raise TankError("Could not find any environments for config %s: %s" % (self.tk, e))
    
        log.info("Found the following environments:")
        for x in envs:
            log.info("    %s" % x)
        log.info("")
        log.info("")
    
        # validate environments
        for env_name in envs:
            env = self.tk.pipeline_configuration.get_environment(env_name)
            _process_environment(log, self.tk, env)
    
        log.info("")
        log.info("")
        log.info("")
            
        # check templates that are orphaned
        unused_templates = set(self.tk.templates.keys()) - g_templates 
    
        log.info("")
        log.info("------------------------------------------------------------------------")
        log.info("The following templates are not being used directly in any environments:")
        log.info("(they may be used inside complex data structures)")
        for ut in unused_templates:
            log.info(ut)
    
        log.info("")
        log.info("")
        log.info("")
        
        # check hooks that are unused
        all_hooks = []
        # get rid of files not ending with .py and strip extension
        for hook in os.listdir(self.tk.pipeline_configuration.get_hooks_location()):
            if hook.endswith(".py"):
                all_hooks.append( hook[:-3] )
        
        unused_hooks = set(all_hooks) - g_hooks 
    
        log.info("")
        log.info("--------------------------------------------------------------------")
        log.info("The following hooks are not being used directly in any environments:")
        log.info("(they may be used inside complex data structures)")
        for uh in unused_hooks:
            log.info(uh)
        
        log.info("")
        log.info("")
        log.info("")
        
        







g_templates = set()
g_hooks = set()

def _validate_bundle(log, tk, name, settings, descriptor):

    log.info("")
    log.info("Validating %s..." % name)

    if not descriptor.exists_local():
        log.info("Please wait, downloading...")
        descriptor.download_local()
    
    #if len(descriptor.get_required_frameworks()) > 0:
    #    log.info("  Using frameworks: %s" % descriptor.get_required_frameworks())
        
    # out of date check
    latest_desc = descriptor.find_latest_version()
    if descriptor.get_version() != latest_desc.get_version():
        log.info(  "WARNING: Latest version is %s. You are running %s." % (latest_desc.get_version(), 
                                                                        descriptor.get_version()))
    
    
    manifest = descriptor.get_configuration_schema()
    
    for s in settings.keys():
        if s not in manifest.keys():
            log.info("  WARNING - Parameter not needed: %s" % s)
        
        else: 
            default = manifest[s].get("default_value")
            
            value = settings[s]
            try:
                validation.validate_single_setting(name, tk, manifest, s, value)
            except TankError, e:
                log.info("  ERROR - Parameter %s - Invalid value: %s" % (s,e))
            else:
                # validation is ok
                if default is None:
                    # no default value
                    # don't report this
                    pass
                    #log.info("  Parameter %s - OK [no default value specified in manifest]" % s)
                
                elif manifest[s].get("type") == "hook" and value == "default":
                    # don't display when default values are used.
                    pass
                    #log.info("  Parameter %s - OK [using hook 'default']" % s)
                
                elif default == value:
                    pass
                    # don't display when default values are used.
                    #log.info("  Parameter %s - OK [using default value]" % s)
                
                else:
                    log.info("  Parameter %s - OK [using non-default value]" % s)
                    log.info("    |---> Current: %s" % value)
                    log.info("    \---> Default: %s" % default)
                    
                # remember templates
                if manifest[s].get("type") == "template":
                    g_templates.add(value)
                if manifest[s].get("type") == "hook":
                    g_hooks.add(value)

                     
    for r in manifest.keys():
        if r not in settings.keys():
            log.error("Required parameter missing: %s" % r)


def _process_environment(log, tk, env):
    
    log.info("Processing environment %s" % env)

    for e in env.get_engines():  
        s = env.get_engine_settings(e)
        descriptor = env.get_engine_descriptor(e)
        name = "Engine %s / %s" % (env.name, e)
        _validate_bundle(log, tk, name, s, descriptor)
        for a in env.get_apps(e):
            s = env.get_app_settings(e, a)
            descriptor = env.get_app_descriptor(e, a)
            name = "%s / %s / %s" % (env.name, e, a)
            _validate_bundle(log, tk, name, s, descriptor)
    
    
    
     





