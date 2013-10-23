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
Methods for handling of the tank command

"""


from .tank_commands.action_base import Action 
from .tank_commands import apps
from .tank_commands import folders
from .tank_commands import misc
from .tank_commands import move_pc
from .tank_commands import move_studio
from .tank_commands import pc_overview
from .tank_commands import migrate_entities
from .tank_commands import path_cache

from ..platform import constants
from ..platform.engine import start_engine, get_environment_from_context
from ..errors import TankError

###############################################################################################
# Built in actions (all in the tank_commands sub module)

BUILT_IN_ACTIONS = [misc.SetupProjectAction, 
                    misc.CoreUpgradeAction, 
                    misc.CoreLocalizeAction,
                    misc.ValidateConfigAction,
                    misc.ClearCacheAction,
                    misc.InteractiveShellAction,
                    apps.InstallAppAction,
                    apps.InstallEngineAction,
                    apps.AppUpdatesAction,
                    folders.CreateFoldersAction,
                    folders.PreviewFoldersAction,
                    move_pc.MovePCAction,
                    pc_overview.PCBreakdownAction,
                    move_studio.MoveStudioInstallAction,
                    migrate_entities.MigratePublishedFileEntitiesAction,
                    path_cache.SynchronizePathCache,
                    path_cache.DeleteFolderAction,
                    path_cache.PathCacheMigrationAction,
                    path_cache.RenameFolderAction,
                    path_cache.PathCacheInfoAction
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
# Shell engine tank commands - bridge for creating an action from an app

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
# Main entry points for accessing tank commands

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
        log.error("Trying to launch %r without an Toolkit instance." % action)
        raise TankError("The command '%s' needs a project to run. For example, if you want "
                        "to run it for project XYZ, execute "
                        "'tank Project XYZ %s'" % (action.name, action.name))
    
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
    Find an action and start execution. 
    
    """
    engine = None

    # first see if we can find the action without starting the engine
    found_action = None
    for x in _get_built_in_actions():
        if x.name == command:
            found_action = x
            break
    
    if found_action and found_action.wants_running_shell_engine == False:
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
        log.info("")
        log.info("")
        log.error("The action '%s' could not be found!" % command)
        log.info("")
        log.info("In order to list all action that are available, try running the same command, " 
                 "but omit the '%s' part at the end." % command)
        log.info("")
    
    else:
        _process_action(code_install_root, 
                        pipeline_config_root, 
                        log, 
                        tk, 
                        ctx, 
                        engine, 
                        found_action, args)
    
