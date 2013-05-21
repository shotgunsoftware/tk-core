"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Methods for handling of the tank command

"""

from . import descriptor
from . import util
from .descriptor import AppDescriptor
from ..util import shotgun
from ..platform import constants
from ..platform import validation
from ..platform.engine import start_engine, get_environment_from_context
from .. import pipelineconfig
from ..errors import TankError, TankEngineInitError
from ..api import Tank
from .. import folder

from . import setup_project, validate_config, administrator, core_api_admin, env_admin

from tank_vendor import yaml

import sys
import os
import shutil

################################################################################################

class Action(object):
    """
    Describes an executable action
    """
    
    # GLOBAL - works everywhere, requires self.code_install_root only
    # PC_LOCAL - works when a PC exists. requires GLOBAL + self.pipeline_config_root + self.tk
    # CTX - works when a context exists. requires PC_LOCAL + self.context
    # ENGINE - works when an engine exists. requires CTX + self.engine 
    GLOBAL, PC_LOCAL, CTX, ENGINE = range(4)
    
    def __init__(self, name, mode, description, category):
        self.name = name
        self.mode = mode
        self.description = description
        self.category = category
        
        # these need to be filled in by calling code prior to execution
        self.tk = None
        self.context = None
        self.engine = None
        self.code_install_root = None
        self.pipeline_config_root = None
        
    def __repr__(self):
        
        mode_str = "UNKNOWN"
        if self.mode == Action.GLOBAL:
            mode_str = "GLOBAL"
        elif self.mode == Action.PC_LOCAL:
            mode_str = "PC_LOCAL"
        elif self.mode == Action.CTX:
            mode_str = "CTX"
        elif self.mode == Action.ENGINE:
            mode_str = "ENGINE"
        
        return "<Action Cmd: '%s' Category: '%s' MODE:%s>" % (self.name, self.category, mode_str)
            
        
    def run(self, log, args):
        raise Exception("Need to implement this")
             
################################################################################################             
             
class SetupProjectAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "setup_project", 
                        Action.GLOBAL, 
                        "Sets up a new project with Tank.", 
                        "Admin")
        
    def run(self, log, args):
        if len(args) != 0:
            raise TankError("This command takes no arguments!")
        setup_project.interactive_setup(log, self.code_install_root)
        
################################################################################################
        
class CoreUpgradeAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "core", 
                        Action.GLOBAL, 
                        "Checks that your Tank Core API install is up to date.", 
                        "Admin")
            
    def run(self, log, args):
        if len(args) != 0:
            raise TankError("This command takes no arguments!")
        if self.code_install_root != self.pipeline_config_root:
            # we are updating a parent install that is shared
            log.info("")
            log.warning("You are potentially about to update the Core API for multiple projects.")
            log.info("")
        core_api_admin.interactive_update(log, self.code_install_root)
    
################################################################################################

class CoreLocalizeAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "localize", 
                        Action.PC_LOCAL, 
                        ("Installs the Core API into your current Configuration. This is typically "
                         "done when you want to test a Core API upgrade in an isolated way. If you "
                         "want to safely test an API upgrade, first clone your production configuration, "
                         "then run the localize command from your clone's tank command."), 
                        "Admin")
    
    def run(self, log, args):
        if len(args) != 0:
            raise TankError("This command takes no arguments!")
        core_api_admin.install_local_core(log, self.code_install_root, self.pipeline_config_root)

################################################################################################

#class MovePCAction(Action):
#    
#    def __init__(self):
#        Action.__init__(self, 
#                        "move_configuration", 
#                        Action.PC_LOCAL, 
#                        ("Moves this configuration from its current disk location to a new location."), 
#                        "Admin")
#    
#    def run(self, log, args):
#        if len(args) != 0:
#            raise TankError("This command takes no arguments!")
#        core_api_admin.install_local_core(log, self.code_install_root, self.pipeline_config_root)

################################################################################################

class PCBreakdownAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "configurations", 
                        Action.PC_LOCAL, 
                        ("Shows an overview of the different configurations registered with this project."), 
                        "Admin")
    
    def run(self, log, args):
        if len(args) != 0:
            raise TankError("This command takes no arguments!")
        
        log.info("Fetching data from Shotgun...")
        project_id = self.tk.pipeline_configuration.get_project_id()
        
        sg = shotgun.create_sg_connection()
        
        proj_data = sg.find_one("Project", [["id", "is", project_id]], ["name"])
        log.info("")
        log.info("")
        log.info("=" * 70)
        log.info("Available Configurations for Project '%s'" % proj_data.get("name"))
        log.info("=" * 70)
        log.info("")
        
        data = sg.find(constants.PIPELINE_CONFIGURATION_ENTITY, 
                       [["project", "is", {"type": "Project", "id": project_id}]],
                       ["code", "users", "mac_path", "windows_path", "linux_path"])
        for d in data:
            
            if len(d.get("users")) == 0:
                log.info("Configuration '%s' (Public)" % d.get("code"))
            else:
                log.info("Configuration '%s' (Private)" % d.get("code"))
                
            log.info("-------------------------------------------------------")
            log.info("")
            
            if d.get("code") == constants.PRIMARY_PIPELINE_CONFIG_NAME:
                log.info("This is the Project Master Configuration. It will be used whenever "
                         "this project is accessed from a studio level tank command or API "
                         "constructor.")
            
            log.info("")
            lp = d.get("linux_path")
            mp = d.get("mac_path")
            wp = d.get("windows_path")
            if lp is None:
                lp = "[Not defined]"
            if wp is None:
                wp = "[Not defined]"
            if mp is None:
                mp = "[Not defined]"
            
            log.info("Linux Location:  %s" % lp )
            log.info("Winows Location: %s" % wp )
            log.info("Mac Location:    %s" % mp )
            log.info("")
            
            
            # check for core API etc. 
            storage_map = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }
            local_path = d.get(storage_map[sys.platform])
            if local_path is None:
                log.info("The Configuration is not accessible from this computer!")
                
            elif not os.path.exists(local_path):
                log.info("The Configuration cannot be found on disk!")
                
            else:
                # yay, exists on disk
                local_tank_command = os.path.join(local_path, "tank")
                
                if os.path.exists(os.path.join(local_path, "install", "core", "_core_upgrader.py")):
                    api_version = pipelineconfig.get_core_api_version_for_pc(local_path)
                    log.info("This configuration is running its own version (%s)"
                             " of the Tank API." % api_version)
                    log.info("If you want to check for core API updates you can run:")
                    log.info("> %s core" % local_tank_command)
                    log.info("")
                    
                else:
                    
                    log.info("This configuration is using a shared version of the Tank API."
                             "If you want it to run its own independent version "
                             "of the Tank Core API, you can run:")
                    log.info("> %s localize" % local_tank_command)
                    log.info("")
                
                log.info("If you want to check for app or engine updates, you can run:")
                log.info("> %s updates" % local_tank_command)
                log.info("")
            
                log.info("If you want to change the location of this configuration, you can run:")
                log.info("> %s move_configuration" % local_tank_command)
                log.info("")
            
            if len(d.get("users")) == 0:
                log.info("This is a public configuration. In Shotgun, the actions defined in this "
                         "configuration will be on all users' menus.")
            
            elif len(d.get("users")) == 1:
                log.info("This is a private configuration. In Shotgun, only %s will see the actions "
                         "defined in this config. If you want to add additional members to this "
                         "configuration, navigate to the Shotgun Pipeline Configuration Page "
                         "and add them to the Users field." % d.get("users")[0]["name"])
            
            elif len(d.get("users")) > 1:
                users = ", ".join( [u.get("name") for u in d.get("users")] )
                log.info("This is a private configuration. In Shotgun, the following users will see "
                         "the actions defined in this config: %s. If you want to add additional "
                         "members to this configuration, navigate to the Shotgun Pipeline "
                         "Configuration Page and add them to the Users field." % users)
            
            log.info("")
            log.info("")
        
        
################################################################################################        

class ValidateConfigAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "validate", 
                        Action.PC_LOCAL, 
                        ("Validates your current Configuration to check that all "
                        "environments have been correctly configured."), 
                        "Admin")
    
    def run(self, log, args):
        if len(args) != 0:
            raise TankError("This command takes no arguments!")
        validate_config.validate_configuration(log, self.tk)

################################################################################################

class ClearCacheAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "clear_cache", 
                        Action.PC_LOCAL, 
                        ("Clears the Shotgun Menu Cache associated with this Configuration. "
                         "This is sometimes useful after complex configuration changes if new "
                         "or modified Tank menu items are not appearing inside Shotgun."), 
                        "Admin")
    
    def run(self, log, args):
        if len(args) != 0:
            raise TankError("This command takes no arguments!")
        
        cache_folder = self.tk.pipeline_configuration.get_cache_location()
        # cache files are on the form shotgun_mac_project.txt
        for f in os.listdir(cache_folder):
            if f.startswith("shotgun") and f.endswith(".txt"):
                full_path = os.path.join(cache_folder, f)
                log.debug("Deleting cache file %s..." % full_path)
                try:
                    os.remove(full_path)
                except:
                    log.warning("Could not delete cache file '%s'!" % full_path)
        
        log.info("The Shotgun menu cache has been cleared.")
        
################################################################################################

class InstallAppAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "install_app", 
                        Action.PC_LOCAL, 
                        "Adds a new app to your tank configuration.", 
                        "Admin")
    
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

################################################################################################

class InstallEngineAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "install_engine", 
                        Action.PC_LOCAL, 
                        "Adds a new engine to your tank configuration.", 
                        "Admin")
    
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

################################################################################################

class AppUpdatesAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "updates", 
                        Action.PC_LOCAL, 
                        "Checks if there are any app or engine updates for the current configuration.", 
                        "Admin")
    
    def run(self, log, args):
        if len(args) != 0:
            raise TankError("Invalid arguments! Run with --help for more details.")
        env_admin.check_for_updates(log, self.tk)

################################################################################################

class CreateFoldersAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "folders", 
                        Action.CTX, 
                        ("Creates folders on disk for your current context. This command is "
                         "typically used in conjunction with a Shotgun entity, for example "
                         "'tank Shot P01 folders' in order to create folders on disk for Shot P01."), 
                        "Production")
    
    def run(self, log, args):
        if len(args) != 0:
            raise TankError("This command takes no arguments!")

        if self.context.project is None:
            log.info("Looks like your context is empty! No folders to create!")
            return

        # first do project
        entity_type = self.context.project["type"]
        entity_id = self.context.project["id"]
        # if there is an entity then that takes precedence
        if self.context.entity:
            entity_type = self.context.entity["type"]
            entity_id = self.context.entity["id"]
        # and if there is a task that is even better
        if self.context.task:
            entity_type = self.context.task["type"]
            entity_id = self.context.task["id"]
        
        log.info("Creating folders, stand by...")
        f = folder.process_filesystem_structure(self.tk, entity_type, entity_id, False, None)
        log.info("")
        log.info("The following items were processed:")
        for x in f:
            log.info(" - %s" % x)
        log.info("")
        log.info("In total, %s folders were processed." % len(f))
        log.info("")

################################################################################################

class PreviewFoldersAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "preview_folders", 
                        Action.CTX, 
                        ("Previews folders on disk for your current context. This command is "
                         "typically used in conjunction with a Shotgun entity, for example "
                         "'tank Shot P01 preview_folders' in order to show what folders "
                         "would be created if you ran the folders command for Shot P01."), 
                        "Production")
    
    def run(self, log, args):
        if len(args) != 0:
            raise TankError("This command takes no arguments!")

        if self.context.project is None:
            log.info("Looks like your context is empty! No folders to preview!")
            return

        # first do project
        entity_type = self.context.project["type"]
        entity_id = self.context.project["id"]
        # if there is an entity then that takes precedence
        if self.context.entity:
            entity_type = self.context.entity["type"]
            entity_id = self.context.entity["id"]
        # and if there is a task that is even better
        if self.context.task:
            entity_type = self.context.task["type"]
            entity_id = self.context.task["id"]

        log.info("Previewing folder creation, stand by...")
        f = folder.process_filesystem_structure(self.tk, entity_type, entity_id, True, None)
        log.info("")
        log.info("The following items were processed:")
        for x in f:
            log.info(" - %s" % x)
        log.info("")
        log.info("In total, %s folders were processed." % len(f))
        log.info("Note - this was a preview and no actual folders were created.")            


################################################################################################




BUILT_IN_ACTIONS = [SetupProjectAction, 
                    CoreUpgradeAction, 
                    CoreLocalizeAction,
                    ValidateConfigAction,
                    ClearCacheAction,
                    InstallAppAction,
                    InstallEngineAction,
                    AppUpdatesAction,
                    CreateFoldersAction,
                    PreviewFoldersAction,
                    #MovePCAction,
                    PCBreakdownAction
                    ]


def _get_built_in_actions():
    """
    Returns a list of built in actions
    """
    actions = []
    for ClassObj in BUILT_IN_ACTIONS:
        actions.append(ClassObj())
    return actions

###############################################################################################
# Shell engine tank commands

class ShellEngineAction(Action):
    """
    Action wrapper around a shell engine command
    """
    def __init__(self, name, description, command_key):
        Action.__init__(self, name, Action.ENGINE, description, "Shell Engine")
        self._command_key = command_key
    
    def run(self, log, args):        
        self.engine.execute_command(self._command_key, args)
        


def get_shell_engine_actions(engine_obj):
    """
    Returns a list of shell engine actions
    """
    
    actions = []
    for c in engine_obj.commands:    
        
        # custom properties dict
        props = engine_obj.commands[c]["properties"]
        
        # the properties dict contains some goodies here that we can use
        # look for a short_name, if that does not exist, fall back on the command name
        # prefix will hold a prefix that guarantees uniqueness, if needed
        cmd_name = c
        if "short_name" in props:
            if props["prefix"]:
                # need a prefix to produce a unique command
                cmd_name = "%s:%s" % (props["prefix"], props["short_name"])
            else:
                # unique without a prefix
                cmd_name = props["short_name"]
        
        description = engine_obj.commands[c]["properties"].get("description", "No description available.")

        actions.append(ShellEngineAction(cmd_name, description, c))

    return actions


###############################################################################################
# Hook based tank commands



def get_actions(log, tk, ctx):
    """
    Returns a list of Action objects given the current context, api etc.
    tk and ctx may be none, indicating that tank is running in a 'partial' state.
    """
    engine = None

    if tk is not None and ctx is not None:          
        # we have all the necessary pieces needed to start an engine
        
        # check if there is an environment object for our context
        env = get_environment_from_context(tk, ctx)
        log.debug("Probing for a shell engine. ctx '%s' --> environment '%s'" % (ctx, env))
        if env and constants.SHELL_ENGINE in env.get_engines():
            log.debug("Looks like the environment has a tk-shell engine. Trying to start it.")
            # we have an environment and a shell engine. Looking good.
            engine = start_engine(constants.SHELL_ENGINE, tk, ctx)        
            log.debug("Started engine %s" % engine)
            log.info("- Started Shell Engine version %s" % engine.version)
            log.info("- Environment: %s." % engine.environment["disk_location"])

        
    actions = []
    
    # get all actions regardless of current scope first
    all_actions = _get_built_in_actions()
    if engine:
        all_actions.extend( get_shell_engine_actions(engine) )
    
    # now only pick the ones that are working with our current state
    for a in all_actions:
        
        if a.mode == Action.GLOBAL:
            # globals are always possible to run
            actions.append(a)
        if tk and a.mode == Action.PC_LOCAL:
            # we have a PC!
            actions.append(a)
        if ctx and a.mode == Action.CTX:
            # we have a command that needs a context
            actions.append(a)
        if engine and a.mode == Action.ENGINE:
            # needs the engine
            actions.append(a)
        
    return (actions, engine)


def _process_action(code_install_root, pipeline_config_root, log, tk, ctx, engine, action, args):
    """
    Does the actual execution of an action object
    """
    # seed the action object with all the handles it may need
    action.tk = tk
    action.context = ctx
    action.engine = engine
    action.code_install_root = code_install_root
    action.pipeline_config_root = pipeline_config_root
    
    # now check that we actually have passed enough stuff to work with this mode
    if action.mode in (Action.PC_LOCAL, Action.CTX, Action.ENGINE) and tk is None:
        # we are missing a tk instance
        log.error("Trying to launch %r without a tank instance." % action)
        raise TankError("The command '%s' needs a project to run." % action.name)
    
    if action.mode in (Action.CTX, Action.ENGINE) and ctx is None:
        # we have a command that needs a context
        log.error("Trying to launch %r without a context." % action)
        raise TankError("The command '%s' needs a work area to run." % action.name)
        
    if action.mode == Action.ENGINE and engine is None:
        # we have a command that needs an engine
        log.error("Trying to launch %r without an engine." % action)
        raise TankError("The command '%s' needs the shell engine running." % action.name)
    
    # ok all good
    log.info("- Running %s..." % action.name)
    log.info("")
    return action.run(log, args)
    
    

def run_action(code_install_root, pipeline_config_root, log, tk, ctx, command, args):
    """
    Find an action and start execution
    """
    engine = None

    # first see if we can find the action without starting the engine
    found_action = None
    for x in _get_built_in_actions():
        if x.name == command:
            found_action = x
            break
    
    if found_action and found_action.mode != Action.ENGINE:
        log.debug("No need to load up the engine for this command.")
    else:
        # try to load the engine.
        if tk is not None and ctx is not None:          
            # we have all the necessary pieces needed to start an engine  
            # check if there is an environment object for our context
            env = get_environment_from_context(tk, ctx)
            log.debug("Probing for a shell engine. ctx '%s' --> environment '%s'" % (ctx, env))
            if env and constants.SHELL_ENGINE in env.get_engines():
                log.debug("Looks like the environment has a tk-shell engine. Trying to start it.")
                # we have an environment and a shell engine. Looking good.
                engine = start_engine(constants.SHELL_ENGINE, tk, ctx)        
                log.debug("Started engine %s" % engine)
                log.info("- Started Shell Engine version %s" % engine.version)
                log.info("- Environment: %s." % engine.environment["disk_location"])
                        
                # now keep looking for our command
                if found_action is None: # may already be found (a core cmd which needs and engine)
                    for x in get_shell_engine_actions(engine):
                        if x.name == command:
                            found_action = x
                            break
                    
    # ok we now have all the pieces we need
    if found_action is None:
        log.error("The command '%s' could not be found!" % command)
    
    else:
        _process_action(code_install_root, 
                        pipeline_config_root, 
                        log, 
                        tk, 
                        ctx, 
                        engine, 
                        found_action, args)
    
   