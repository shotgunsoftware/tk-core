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

import logging

from .tank_commands.action_base import Action 
from .tank_commands import folders
from .tank_commands import misc
from .tank_commands import move_pc
from .tank_commands import move_studio
from .tank_commands import pc_overview
from .tank_commands import migrate_entities
from .tank_commands import update
from .tank_commands import push_pc
from .tank_commands import setup_project
from .tank_commands import validate_config
from .tank_commands import cache_apps
from .tank_commands import switch
from .tank_commands import app_info
from .tank_commands import core
from .tank_commands import install

from ..platform import constants
from ..platform.engine import start_engine, get_environment_from_context
from ..errors import TankError

###############################################################################################
# Built in actions (all in the tank_commands sub module)

BUILT_IN_ACTIONS = [setup_project.SetupProjectAction, 
                    core.CoreUpgradeAction, 
                    core.CoreLocalizeAction,
                    validate_config.ValidateConfigAction,
                    cache_apps.CacheAppsAction,
                    misc.ClearCacheAction,
                    switch.SwitchAppAction,
                    app_info.AppInfoAction,
                    misc.InteractiveShellAction,
                    install.InstallAppAction,
                    push_pc.PushPCAction,
                    install.InstallEngineAction,
                    update.AppUpdatesAction,
                    folders.CreateFoldersAction,
                    folders.PreviewFoldersAction,
                    move_pc.MovePCAction,
                    pc_overview.PCBreakdownAction,
                    move_studio.MoveStudioInstallAction,
                    migrate_entities.MigratePublishedFileEntitiesAction
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
# Shell engine tank commands - adapter for creating an action from an app

class ShellEngineAction(Action):
    """
    Action wrapper around a shell engine command
    """
    def __init__(self, name, description, command_key):
        Action.__init__(self, name, Action.ENGINE, description, "Shell Engine")
        self._command_key = command_key
    
    def run_interactive(self, log, args):        
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
# Complete public API definitions for accessing toolkit commands
# ------------------------------------------------------------
# - The list_commands returns a list of available command names
# - The create_command factory returns a SgtkSystemCommand class instance
#   for a given command
# - The SgtkSystemCommand class wraps around a command implementation and
#   forms the actual interface which we expose via the interface.   

def list_commands():
    """
    Lists the system commands registered with the system.

    :returns: list of command names
    """
    action_names = []
    for a in _get_built_in_actions():
        if a.supports_api:
            action_names.append(a.name)    
    return action_names

def create_command(command_name):
    """
    Creates a command object that can be used to execute a command
    
    :returns: SgtkSystemCommand object instance
    """
    for x in _get_built_in_actions():
        if x.name == command_name and x.supports_api:
            return SgtkSystemCommand(x)
    # not found
    raise TankError("The command '%s' does not exist. Use the list_commands method to "
                    "see a list of all commands available via the API." % command_name)


class SgtkSystemCommand(object):
    """
    Represents a toolkit system command.
    
    Toolkit commands can be one of two different types:
    
    - A global command executes without any type of state or context. 
      Examples of global commands include setup_project, which can be 
      carried out from an empty state without any project specified or
      any type of normal toolkit environment present.
    - A command that requires an API instance needs to be initialized
      with a sgtk API instance in order to execute. The tk instance 
      defines the pipeline configuration to use and which project to run.
      Most commmands are of this class. For this command class to work,
      the needs_
      
     You can query if an api instance is needed using the command_instance.needs_api
     property. If this returns true, a api_instance parameter must be passed to
     the execute() method when the command is executed. 
    """
    
    # this class wraps around a tank.deploy.tank_commands.action_base.Action class
    # and exposes the "official" interface for it.
    
    def __init__(self, pimpl):
        self.__pimpl = pimpl
        
        # set up a default logger which can be overridden via the set_logger method
        self.__log = logging.getLogger("sgtk.systemcommand")
        self.__log.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)s %(message)s")
        ch.setFormatter(formatter)
        self.__log.addHandler(ch)
        
        # only commands of type GLOBAL, PC_LOCAL are currently supported
        if self.__pimpl.mode not in (Action.GLOBAL, Action.PC_LOCAL):
            raise TankError("The command %r is not of a type which is supported by Toolkit. "
                            "Please contact support on toolkitsupport@shotgunsoftware.com" % self.__pimpl)
        
    @property
    def needs_api(self):
        """
        Returns true if a sgtk API is required to execute this command.
        If so, an API instance needs to be passed to the execute method when the command
        is executed.
        """
        return (self.__pimpl.mode == Action.PC_LOCAL)

    @property
    def description(self):
        """
        Returns a description of this command.
        """
        return self.__pimpl.description
         
    @property
    def name(self):
        """
        Returns the name of this command.
        """
        return self.__pimpl.name

    @property
    def optional_parameters(self):
        """
        Returns a dictionary of all optional parameters. The key is
        the parameter name and the value is the description.
        """
        return self.__pimpl.optional_properties

    @property
    def required_properties(self):
        """
        Returns a dictionary of required parameter. The key is
        the parameter name and the value is the description.
        """
        return self.__pimpl.required_properties
        
    def set_logger(self, log):
        """
        Specify a standard python log instance to send logging output to.
        If this is not specify, the standard output mechanism will be used.
        
        :param log: Standard python logging instance
        """
        self.__log = log

    def execute(self, params, api_instance=None):
        """
        Execute this command.
        
        :param params: dictionary of parameters to pass to this command.
                       the dictionary key is the name of the parameter and the value
                       is the value you want to pass. You can query which parameters
                       can be passed in using the required_parameters and optional_parameters
                       class accessors.
        :param api_instane: For commands which require a Toolkit API instance to operate, 
                            pass it in via this parameter. You can find out if a command
                            requires this via the needs_api property. 
        """
        
#        if api_instance:
#            self.
            
        self.__pimpl.run_noninteractive(self.__log, params)
        
        
        
    
    
    
###############################################################################################
# Main entry points for accessing tank commands from the tank command / shell engine

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
        log.debug("Trying to launch %r without an Toolkit instance." % action)
        raise TankError("The command '%s' needs a project to run. For example, if you want "
                        "to run it for project XYZ, execute "
                        "'tank Project XYZ %s'" % (action.name, action.name))
    
    if action.mode in (Action.CTX, Action.ENGINE) and ctx is None:
        # we have a command that needs a context
        log.debug("Trying to launch %r without a context." % action)
        raise TankError("The command '%s' needs a work area to run." % action.name)
        
    if action.mode == Action.ENGINE and engine is None:
        # we have a command that needs an engine
        log.debug("Trying to launch %r without an engine." % action)
        raise TankError("The command '%s' needs the shell engine running." % action.name)
    
    # ok all good
    log.info("- Running command %s..." % action.name)
    log.info("")
    log.info("")
    log.info("-" * 70)
    log.info("Command: %s" % action.name.replace("_", " ").capitalize())
    log.info("-" * 70)
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
    
