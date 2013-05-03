#
# Copyright (c) 2012 Shotgun Software, Inc
# ----------------------------------------------------


import sys
import os
import cgi
import re
import logging
import tank
import textwrap
from tank import TankError, TankEngineInitError
from tank.deploy import setup_project, validate_config, administrator, core_api_admin, env_admin
from tank import pipelineconfig
from tank.util import shotgun
from tank.platform import engine
from tank import folder

SHOTGUN_ENTITY_TYPES = ['Playlist', 'AssetSceneConnection', 'Note', 'TaskDependency', 'PageHit', 
                        'ActionMenuItem', 'Attachment', 'AssetMocapTakeConnection', 
                        'Department', 'Group', 'PlaylistVersionConnection', 
                        'Booking', 'CutVersionConnection', 'CameraMocapTakeConnection', 
                        'AssetElementConnection', 'ReleaseTicketConnection', 
                        'RevisionRevisionConnection', 'MocapTakeRangeShotConnection', 'TimeLog', 
                        'Step', 'AssetBlendshapeConnection', 'PerformerMocapTakeConnection', 
                        'Phase', 'Ticket', 'AssetShotConnection', 'TicketTicketConnection', 
                        'Icon', 'PageSetting', 'Status', 'Reply', 'Task', 'ApiUser', 
                        'ProjectUserConnection', 'LaunchShotConnection', 'ShotShotConnection', 
                        'PerformerRoutineConnection', 'AppWelcomeUserConnection', 'HumanUser', 
                        'Project', 'LocalStorage', 'TaskTemplate', 'RevisionTicketConnection', 
                        'PerformerShootDayConnection', 'PipelineConfiguration', 'LaunchSceneConnection', 
                        'GroupUserConnection', 'AssetSequenceConnection', 'Page', 
                        'ShootDaySceneConnection', 'TankType', 'PhysicalAssetMocapTakeConnection', 
                        'Shot', 'TankPublishedFile', 'Sequence', 'BannerUserConnection', 
                        'AssetAssetConnection', 'Version', 'ElementShotConnection', 
                        'PermissionRuleSet', 'EventLogEntry', 'TankDependency', 
                        'AssetShootDayConnection', 'Asset']

# built in commands that can run without a project
CORE_NON_PROJECT_COMMANDS = ["setup_project", "core", "folders"]

# built in commands that run against a specific project
CORE_PROJECT_COMMANDS = ["validate", 
                         "shotgun_run_action", 
                         "shotgun_cache_actions", 
                         "updates",
                         "clear_cache",
                         "install_app",
                         "install_engine"]

SHELL_ENGINE = "tk-shell"

class AltCustomFormatter(logging.Formatter):
    """ 
    Custom logging output
    """
    def __init__(self, *args, **kwargs):
        # passthrough so we can init stuff
        self._html = False
        self._num_items = 0
        logging.Formatter.__init__(self, *args, **kwargs)
    
    def enable_html_mode(self):
        self._html = True
    
    def get_num_items(self):
        return self._num_items
    
    def format(self, record):
        
        if self._html:
            # html logging for shotgun. 
            # The logging mechanisms in Shotgun tend to filter out any output
            # which does not start with an html tag, so we need to make sure we got that.
            if record.levelno in (logging.WARNING, logging.ERROR, logging.CRITICAL, logging.DEBUG):
                # for errors and warnings, we turn all special chars into codes using cgi
                message = "<b>%s:</b> %s" % (record.levelname, cgi.escape(record.msg)) 
            else:
                # info logging allows html chars to be passed so no cgi encode
                message = record.msg
            
            # now make sure each distinct line is wrapped in a span so the shotgun 
            # logger will pick them up.
            lines = []
            for line in message.split("\n"):
                lines.append("<span>%s</span>" % line)
                
            record.msg = "\n".join(lines)
            
        else:
            # shell based logging. Cut nicely at 80 chars width.        
            if record.levelno in (logging.WARNING, logging.ERROR, logging.CRITICAL, logging.DEBUG):
                record.msg = '%s: %s' % (record.levelname, record.msg)
            
            if "Code Traceback" not in record.msg:
                # do not wrap exceptions 
                lines = []
                for x in textwrap.wrap(record.msg, width=78):
                    lines.append(x)
                record.msg = "\n".join(lines)
        
        self._num_items += 1        
        return logging.Formatter.format(self, record)
    

def show_help(log):

    info = """
Welcome to Tank!

This command lets you run control tank from a shell. You can run apps and 
engines via the Tank command. You can also run various tank admin commands.


General options and info
----------------------------------------------
- To show this help, add a -h or --help flag.
- To display verbose debug, add a --debug flag.


Running Apps
----------------------------------------------
Syntax: tank [context] command [args]

 - Context is a location on disk where you want the tank command to operate. 
   It can also be a Shotgun Entity on the form Type id or Type name describing
   the object you want to operate on. If you leave this out, the tank command 
   will use your current working directory as the context.

 - Command is the engine command to execute. If you leave this out, Tank will
   list the available commands.

Examples:

Show what commands are available for the current directory:
> tank

Show what commands are available for Shot ABC123
> tank Shot ABC123

Launch maya for your current path (assuming this command exists):
> tank launch_maya

Launch maya for a Shot in Shotgun:
> tank Shot ABC123 launch_maya

Launch maya for a Task in Shotgun using an id:
> tank Task 234 launch_maya

Launch maya for a folder:
> tank /studio/proj_xyz/shots/ABC123 launch_maya


Administering Tank
----------------------------------------------

The following admin commands are available:

> tank setup_project - create a new project
> tank folders entity_type name [--preview] -- create new folders on disk
> tank validate - validates your configuration
> tank core - Check version and update the Core API.
> tank core localize - run a local version of the core API
> tank clear_cache - clears the tank shotgun actions cache

> tank install_app - installs a new app from the tank store.
> tank install_engine - installs a new engine from the tank store.
> tank updates - check for updates to apps and engines

Note! Additional configuration is available inside of Shotgun.


"""
    for x in info.split("\n"):
        log.info(x)
    
    
def _run_shotgun_command(log, tk, action_name, entity_type, entity_ids):
    """
    Helper method. Starts the shotgun engine and 
    executes a command.
    """
    
    # add some smarts about context management here
    if len(entity_ids) == 1:
        # this is a single selection
        ctx = tk.context_from_entity(entity_type, entity_ids[0])
    else:
        # with multiple items selected, create a blank context
        ctx = tk.context_empty()

    # start the shotgun engine, load the apps
    e = engine.start_shotgun_engine(tk, entity_type, ctx)

    cmd = e.commands.get(action_name)
    if cmd:
        callback = cmd["callback"]
        # introspect and get number of args for this fn
        arg_count = callback.func_code.co_argcount
        
        # check if we are running a pre-013 engine 
        # (this can be removed at a later point)
        if hasattr(e, "execute_old_style_command"): 
            # 013 compliant engine!
            # choose between simple style callbacks or complex style
            # special shotgun callbacks - these always take two
            # params entity_type and entity_ids            
            if arg_count > 1:
                # old style shotgun app launch - takes entity_type and ids as args
                e.execute_old_style_command(action_name, entity_type, entity_ids)
            else:
                # std tank app launch
                e.execute_command(action_name)
        else:
            # engine that is pre-013
            # this engine does not have any specific callbacks
            # all apps that are pre-013 take two args
            callback(entity_type, entity_ids)
            
    else:
        # unknown command - this typically is caused by apps failing to initialize.
        e.log_error("The action could not be executed! This is typically because there "
                    "is an error in the app configuration which prevents the engine from "
                    "initializing it.")
    
    
def _write_shotgun_cache(tk, entity_type, cache_file_name):
    """
    Writes a shotgun cache menu file to disk.
    The cache is per type and per operating system
    """
                
    cache_path = os.path.join(tk.pipeline_configuration.get_cache_location(), cache_file_name)
    
    # start the shotgun engine, load the apps
    e = engine.start_shotgun_engine(tk, entity_type)
    
    # get list of actions
    engine_commands = e.commands
    
    # insert special system commands
    if entity_type == "Project":
        engine_commands["__core_info"] = { "properties": {"title": "Check for Core Upgrades...",
                                                          "deny_permissions": ["Artist"] } }
        
        engine_commands["__upgrade_check"] = { "properties": {"title": "Check for App Upgrades...",
                                                              "deny_permissions": ["Artist"] } }

    # extract actions into cache file
    res = []
    for (cmd_name, cmd_params) in engine_commands.items():
        
        # some apps provide a special deny_platforms entry
        if "deny_platforms" in cmd_params["properties"]:
            # setting can be Linux, Windows or Mac
            curr_os = {"linux2": "Linux", "darwin": "Mac", "win32": "Windows"}[sys.platform]
            if curr_os in cmd_params["properties"]["deny_platforms"]:
                # deny this platform! :)
                continue
        
        if "title" in cmd_params["properties"]:
            title = cmd_params["properties"]["title"]
        else:
            title = cmd_name
            
        if "supports_multiple_selection" in cmd_params["properties"]:
            supports_multiple_sel = cmd_params["properties"]["supports_multiple_selection"]
        else:
            supports_multiple_sel = False
            
        if "deny_permissions" in cmd_params["properties"]:
            deny = ",".join(cmd_params["properties"]["deny_permissions"])
        else:
            deny = ""
        
        entry = [ cmd_name, title, deny, str(supports_multiple_sel) ]
        
        res.append("$".join(entry))

    data = "\n".join(res)

    try:
        # if file does not exist, make sure it is created with open permissions    
        cache_file_created = False
        if not os.path.exists(cache_path):
            cache_file_created = True
        
        # Write to cache file
        f = open(cache_path, "wt")
        f.write(data)
        f.close()
        
        # make sure cache file has proper permissions
        if cache_file_created:
            old_umask = os.umask(0)
            try:
                os.chmod(cache_path, 0666)
            finally:
                os.umask(old_umask)
                            
    except Exception, e:
        raise TankError("Could not write to cache file %s: %s" % (cache_path, e))
    


def run_core_non_project_command(log, install_root, pipeline_config_root, command, args):
    """
    Execute one of the built in commands
    """
    log.debug("Running built in command %s" % command)
    log.debug("Arguments passed: %s" % args)
 

    if command == "setup_project":
        # project setup
        if len(args) != 0:
            raise TankError("Invalid arguments. Run tank --help for more information.")
        
        setup_project.interactive_setup(log, install_root)
        
    elif command == "folders":
        # info about all PCs etc.
        if len(args) not in [2, 3]:
            raise TankError("Invalid arguments. Run tank --help for more information.")

        log.info("")
        
        # handle preview mode
        preview = False
        if "--preview" in args:
            preview = True
            # remove this arg
            args = [arg for arg in args if arg != "--preview"]
        
        # fetch other options
        entity_type = args[0]
        item = args[1]
        
        log.info("Will process folders for %s %s" % (entity_type, item))        
        
        # first find project
        sg = shotgun.create_sg_connection()
        
        # check if item is an id, in that case use it directly, otherwise look it up
        try:
            sg_id = int(item)
        except:
            # it wasn't an id, so resolve it
            entity = sg.find(entity_type, [["code", "is", item]])
            if len(entity) == 0:
                raise TankError("Could not find %s '%s' in Shotgun!" % (entity_type, item))
            elif len(entity) > 1:
                raise TankError("More than one item matching %s '%s'. Please specify a shotgun id "
                                "instead of a name (e.g tank folders %s 1234)" % (item, entity_type))
            else:
                # single match yay
                sg_id = entity[0]["id"]
                
        # now create a tank 
        tk = tank.tank_from_entity(entity_type, sg_id)
        try:
            if preview:
                log.info("Previewing folder creation, stand by...")
            else:
                log.info("Creating folders, stand by...")
                
            f = folder.process_filesystem_structure(tk, entity_type, sg_id, preview, None)
            log.info("Folder creation complete!")
            log.info("")
            log.info("The following items were processed:")
            for x in f:
                log.info(" - %s" % x)
                
            log.info("")
            log.info("In total, %s folders were processed." % len(f))
            if preview:
                log.info("Note: No folders were created, preview mode only.")
            log.info("")
            
        except TankError, e:
            log.error("Folder Creation Error: %s" % e)
            

    elif command == "core":
        # update the core in this pipeline config
        
        # core update > update to latest
        # core        > info about which PCs are using this core + help
        # core install  > get local core
        
        if len(args) == 0:
            
            if install_root != pipeline_config_root:
                # we are updating a parent install that is shared
                log.info("")
                log.warning("You are potentially about to update the Core API for multiple projects.")
                log.info("")
            
            core_api_admin.interactive_update(log, install_root)

        elif len(args) == 1 and args[0] == "localize":
            # a special case which actually requires a pipeline config object
            try:
                pc = pipelineconfig.from_path(pipeline_config_root)            
            except TankError, e:
                raise TankError("You must run the core install command against a specific "
                                "Tank Configuration, not against a shared core location. "
                                "Navigate to the Tank Configuration you want to operate on, "
                                "and run the tank command from there. Details: %s" % e)
            
            core_api_admin.install_local_core(log, pc, install_root, pipeline_config_root)
        
        else:
            raise TankError("Invalid arguments! Please run tank --help for more information.")
        
    else:
        raise TankError("Unknown command '%s'. Run tank --help for more information" % command)



def run_core_project_command(log, install_root, pipeline_config_root, command, args):
    """
    Execute one of the built in commands
    """
    
    log.debug("Running built in command %s" % command)
    log.debug("Arguments passed: %s" % args)
 
    if pipeline_config_root is None:
        
        log.info("")
        log.info("The '%s' command is configuration specific. This means that you need to "
                  "run it against a specific pipeline configuration or project rather than "
                  "the generic studio tank command. Below is a list of the available "
                  "pipeline configurations and their tank commands:" % command )
        
        # present a list of the possible tank commands
        sg = tank.util.shotgun.create_sg_connection()
        current_user = tank.util.login.get_shotgun_user(sg)
        current_user_id = None
        if current_user:
            current_user_id = current_user["id"]
        data = sg.find("PipelineConfiguration", 
                       [], 
                       ["code", "users", "project", "linux_path", "windows_path", "mac_path", "project"])
        
        log.info("")
        for pc in data:
            
            associated_user_ids = [ x["id"] for x in pc["users"] ]
            
            if len(associated_user_ids) > 0 and current_user_id not in associated_user_ids:
                # not our user sandbox
                continue
            
            curr_path = {"linux2":"linux_path", "win32":"windows_path", "darwin":"mac_path" }[sys.platform]
            
            if pc[curr_path] is None:
                continue
            
            tank_cmd = os.path.join(pc[curr_path], "tank")
            
            log.info("Project %s (%s)" % (pc["project"]["name"], pc["code"]))
            log.info("> %s" % tank_cmd)
            log.info("")
            
        raise TankError("Try executing the command against one of the project specific " 
                        "tank commands in the list above!")
        
    try:
        tk = tank.tank_from_path(pipeline_config_root)
        # attach our logger to the tank instance
        # this will be detected by the shotgun and shell engines
        # and used.
        tk.log = log
    except TankError, e:
        raise TankError("Could not instantiate a Tank API Object! Details: %s" % e )

    if command == "validate":
        # validate a pipeline config        
        if len(args) != 0:
            raise TankError("Invalid arguments. Run tank --help for more information.")
        validate_config.validate_configuration(log, tk)

    elif command == "shotgun_run_action":
        
        # we are talking to shotgun! First of all, make sure we switch on our html style logging
        log.handlers[0].formatter.enable_html_mode()

        # params: action_name, entity_type, entity_ids
        if len(args) != 3:
            raise TankError("Invalid arguments! Pass action_name, entity_type, comma_separated_entity_ids")

        # wrap in a big try-catch so that we handle error feedback rather than letting it through
        # into the big master trap (which is designed for command line interaction)
        try:

            action_name = args[0]   
            entity_type = args[1]
            entity_ids_str = args[2].split(",")
            entity_ids = [int(x) for x in entity_ids_str]   
            
            if action_name == "__clone_pc":
                # special data passed in entity_type: USER_ID:NEW_PATH
                user_id = int(entity_type.split(":")[0])
                new_name = entity_type.split(":")[1]
                new_path_linux = entity_type.split(":")[2]
                new_path_mac = entity_type.split(":")[3]
                new_path_windows = ":".join(entity_type.split(":")[4:])
                pc_entity_id = entity_ids[0]      
                source_pc_has_shared_core_api = (install_root != pipeline_config_root)     
                administrator.clone_configuration(log, 
                                                  tk, 
                                                  pc_entity_id,
                                                  user_id, 
                                                  new_name,
                                                  new_path_linux, 
                                                  new_path_mac, 
                                                  new_path_windows,
                                                  source_pc_has_shared_core_api)
                        
            elif action_name == "__core_info":            
                core_api_admin.show_core_info(log, install_root, pipeline_config_root)
    
            elif action_name == "__upgrade_check":
                core_api_admin.show_upgrade_info(log, install_root, pipeline_config_root)
            else:        
                _run_shotgun_command(log, tk, action_name, entity_type, entity_ids)
            
        except TankError, e:
            log.error("Could not execute command! Details: %s" % e)
    
    elif command == "shotgun_cache_actions":
        
        # we are talking to shotgun! First of all, make sure we switch on our html style logging
        log.handlers[0].formatter.enable_html_mode()
        
        
        # params: entity_type, cache_file_name
        if len(args) != 2:
            raise TankError("Invalid arguments! Pass entity_type, cache_file_name")
        
        entity_type = args[0]
        cache_file_name = args[1]

        num_log_messages_before = log.handlers[0].formatter.get_num_items()    
        try:            
            _write_shotgun_cache(tk, entity_type, cache_file_name)
        except TankError, e:
            log.error("Error writing shotgun cache file: %s" % e)
        except Exception, e:
            log.exception("A general error occurred.")
        num_log_messages_after = log.handlers[0].formatter.get_num_items()
        
        # check if there were any log output. This is an indication that something
        # weird and unexpected has happened...
        if (num_log_messages_after - num_log_messages_before) > 0:
            log.info("")
            log.warning("Generating the cache file for this environment may have resulted in some "
                        "actions being omitted because of configuration errors. You may need to "
                        "clear the cache by running the following command:")
            
            code_css_block = "display: block; padding: 0.5em 1em; border: 1px solid #bebab0; background: #faf8f0;"
        
            log.info("")
            if sys.platform == "win32":
                tank_cmd = os.path.join(pipeline_config_root, "tank.bat")
            else:
                tank_cmd = os.path.join(pipeline_config_root, "tank")
            log.info("<code style='%s'>%s clear_cache</code>" % (code_css_block, tank_cmd))
            log.info("")
        
    elif command == "clear_cache":
        cache_folder = tk.pipeline_configuration.get_cache_location()
        # cache files are on the form shotgun_mac_project.txt
        for f in os.listdir(cache_folder):
            if f.startswith("shotgun") and f.endswith(".txt"):
                full_path = os.path.join(cache_folder, f)
                log.debug("Deleting cache file %s..." % full_path)
                os.remove(full_path) 
        
    elif command == "install_app":
        
        if len(args) != 3:
            raise TankError("Invalid arguments! Syntax: install_app environment_name engine_name app_name")
        env_name = args[0]   
        engine_name = args[1]
        app_name = args[2]
        env_admin.install_app(log, tk, env_name, engine_name, app_name)
        
    elif command == "install_engine":

        if len(args) != 2:
            raise TankError("Invalid arguments! Syntax: install_engine environment_name engine_name")
        env_name = args[0]
        engine_name = args[1]   
        env_admin.install_engine(log, tk, env_name, engine_name)

    elif command == "updates":

        if len(args) != 0:
            raise TankError("Invalid arguments! Run with --help for more details.")
        env_admin.check_for_updates(log, tk)

    else:
        raise TankError("Unknown command '%s'. Run tank --help for more information" % command)



def run_engine_cmd(log, install_root, pipeline_config_root, context_items, command, using_cwd, args):
    """
    Launches an engine and potentially executed a command.
    
    :param log: logger
    :param install_root: tank installation
    :param pipeline_config_root: PC config location
    :param context_items: list of strings to describe context. Either ["path"], 
                               ["entity_type", "entity_id"] or ["entity_type", "entity_name"]
    
    :param engine_name: engine to run
    :param command: command to run - None will display a list of commands
    :param using_cwd: Was the context passed based on the current work folder?
    """
    log.debug("")
    log.debug("Will start engine %s" % SHELL_ENGINE)
    log.debug("Context items: %s" % str(context_items))    
    log.debug("Command: %s" % command)
    log.debug("Additional args: %s" % str(args))

    log.info("")
    log.info("Welcome to Tank!")

    # now resolve the location and start      
    if len(context_items) == 1:        
        # context str is a path
        uses_shotgun_context = False
        ctx_path = context_items[0]
        try:
            tk = tank.tank_from_path(ctx_path)
        except TankError, e:
            # this path was not right. Fall back on default message
            if using_cwd:
                if command is None:
                    # someone just ran "tank" in CWD
                    raise TankError("Your current directory (%s) is not associated with "
                                    "any Tank setup. Try navigating to a folder inside a Tank "
                                    "project and running the tank command there to see a listing "
                                    "of all the commands that are available. Alternatively, you can "
                                    "do maintenance and admin operations using the Tank command - "
                                    "for a list of options, run tank with the --help parameter. "
                                    "(Detailed error message: %s)" % (ctx_path, e))
                else: 
                    # someone ran tank COMMAND
                    raise TankError("You are trying to start run the command '%s' in your "
                                    "current working directory (%s) but looks like Tank Reported "
                                    "a problem. Details: %s" % (command, ctx_path, e))
            else:
                # a bad path was specified by a user
                raise TankError("Could not launch Tank from path '%s'! "
                                "Details: %s" % (ctx_path, e) )
            
        log.debug("Resolved path %s into tank instance %s" % (ctx_path, tk))
        
    else:
        # Shot 123 or Shot Foo        
        uses_shotgun_context = True
        entity_type = context_items[0]
        item = context_items[1]
        try:
            entity_id = int(item)
        except:
            # it wasn't an id. So resolve the id
            sg = shotgun.create_sg_connection()
            
            name_field = "code"
            if entity_type == "Project":
                name_field = "name"
            elif entity_type == "Task":
                name_field = "content"
            elif entity_type == "HumanUser":
                name_field = "login"
            
            try:       
                entities = sg.find(entity_type, 
                                   [[name_field, "contains", item]], 
                                   [name_field, "description", "entity", "link"])
            except Exception, e:
                
                # API read() invalid/missing string entity 'type'
                if str(e).startswith("API read() invalid/missing string entity 'type'"):
                    # bad entity type
                    raise TankError("The entity type '%s' does not exist in Shotgun!" % entity_type)
                else:
                    # some other error
                    raise TankError("An error occurred when searching in Shotgun: %s" % e)
                 
            if len(entities) == 0:
                log.info("")
                log.error("Could not find a %s with a name containing '%s' in Shotgun!" % (entity_type, item))
                raise TankError("Try searching for something more else, alternatively use a "
                                "Shotgun id to locate your object. For more information, run "
                                "tank --help.")
            
            elif len(entities) > 1:
                log.info("")
                log.error("More than one item matching %s '%s'!" % (entity_type, item))
                log.info("")
                log.info("Found the following %ss:" % entity_type)
                for x in entities:
                    chunks = []
                    chunks.append(" [%d] %s" % (x["id"], x[name_field]))
                    
                    if x.get("entity"):
                        try: # <-- in case this is ever not a link field
                            chunks.append( " (%s %s)" % (x.get("entity").get("type"), 
                                                         x.get("entity").get("name")))
                        except:
                            pass
                    
                    if x.get("link"):
                        try: # <-- in case this is ever not a link field
                            chunks.append( " (%s %s)" % (x.get("link").get("type"), 
                                                         x.get("link").get("name")))
                        except:
                            pass

                    if x.get("description"):
                        desc = x.get("description")
                        # now use the rest of our line for desc.
                        chars_used = sum([len(x) for x in chunks])
                        chars_available = 60 - chars_used
                        # clever regex to chop on word boundaries
                        chopped_desc = re.match(r'(.{,%d})(\W|$)' % chars_available, desc).group(1)
                        if len(chopped_desc) < len(desc):
                            chopped_desc += "..."
                        chunks.append( " (%s)" % chopped_desc)
                    
                    log.info("".join(chunks))
                
                raise TankError("Please specify a full name from the list above! If there are "
                                "more than one item with the same name, you can use the [id] instead.")
            else:
                # single match yay
                entity = entities[0]
                log.info("- Found %s %s" % (entity_type, entity[name_field]))
                entity_id = entity["id"]
            
        # sweet we got a type and an id. Start up tank.
        try:
            tk = tank.tank_from_entity(entity_type, entity_id)
        except TankError, e:
            # invalid entity
            raise TankError("Could not start up Tank! Details: %s" % e)
            
        log.debug("Resolved %s %s into tank instance %s" % (entity_type, item, tk))
    
    if install_root != pipeline_config_root:
        # generic tank command - so indicate which config was picked
        log.info("- Starting Tank %s from %s." % (tk.version, tk.pipeline_configuration.get_path()))
    else:
        log.info("- Starting Tank %s." % tk.version)
        
    
    # attach our logger to the tank instance
    # this will be detected by the shotgun and shell engines
    # and used.
    tk.log = log
        
    # and create a context
    if uses_shotgun_context:
        ctx = tk.context_from_entity(entity_type, entity_id)
    else:
        ctx = tk.context_from_path(ctx_path)
    log.debug("Resolved %s into context %r" % (" ".join(context_items), ctx))
    log.info("- Setting the Context to %s." % ctx)
            
    # kick off mr engine.
    try:
        e = tank.platform.start_engine(SHELL_ENGINE, tk, ctx)
    except TankEngineInitError, err:
        local_tank_cmd = os.path.join(tk.pipeline_configuration.get_path(), "tank")
        # now try to figure out the environment to use
        # note that this may raise exceptions too, caught by the main trap
        try:
            env = tank.platform.engine.get_environment_from_context(tk, ctx)
        except TankError, e:
            raise TankError("Could not start the Tank Shell Engine! Tank could not determine "
                            "which environment configuration to use for your current context. "
                            "Details: %s" % e)
        # ok we got the context, the environment but the engine wouldn't start. Most likely
        # because it does not exist in that environment.
        raise TankError("Could not start the Tank Shell Engine! For the tank command to be able "
                        "to run apps, the shell engine needs to be installed. "
                        "You can install it by running the command '%s install_engine %s %s'. "
                        "(Error details: %s) " % (local_tank_cmd, env.name, SHELL_ENGINE, err))
                
    log.debug("Started engine %s" % e)
    
    env_name = e.environment["name"].capitalize()
    log.info("- Loaded the %s environment." % env_name)

    # lastly, run the command
    command_found = True
        
    if command is None:
        log.info("")
        log.info("You didn't specify a command to run!")
        command_found = False

    ########################################################################
    # make a list of commands, format them and make them look nice
    
    formatted_commands = {}
    for c in e.commands:    
        
        # custom properties dict
        props = e.commands[c]["properties"]
        
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
        
        description = e.commands[c]["properties"].get("description", "No description available.")

        formatted_commands[cmd_name] = {"description": description, "key": c}

          
    if command is not None and command not in formatted_commands:
        log.info("")
        log.error("Unknown command: '%s'" % command)
        command_found = False
        
    if command_found:
        # run the app!
        log.info("Executing the %s command." % command)
        cmd_key = formatted_commands[command]["key"]
        # special shell engine specific method  
        return e.execute_command(cmd_key, args)

    elif len(formatted_commands) == 0:
        log.info("")
        log.info("There are no commands currently registered!")
        log.info("")
        
        local_tank_cmd = os.path.join(e.tank.pipeline_configuration.get_path(), "tank")
        env_name = e.environment["name"]
        
        log.info("In order to add apps, you need to run the install_app command."
                 "For example, in order to install the work area info app, execute "
                 "the following command:")
        log.info("> %s install_app %s %s tk-multi-about" % (local_tank_cmd, env_name, SHELL_ENGINE))
        log.info("")
        
    else:
        log.info("")
        log.info("The following commands are available:")
        log.info("")
        
        for c in formatted_commands:    
            log.info("- %s" % c)
            log.info("  %s" % formatted_commands[c]["description"])
            log.info("")
            
        log.info("")
        log.info("  To run a command in the current work area, type 'tank command'")
        log.info("  To run a command for a folder, type 'tank /path/to/location command'" )
        log.info("  To run a command for a Shotgun item, type 'tank Shot ABC command'" )
        
        log.info("")
        log.info("")
    
            



if __name__ == "__main__":    

    # set up logging channel for this script
    log = logging.getLogger("tank.setup_project")
    log.setLevel(logging.INFO)
    
    ch = logging.StreamHandler(sys.stdout)
    formatter = AltCustomFormatter()
    ch.setFormatter(formatter)
    log.addHandler(ch)

    # the first argument is always the path to the code root
    # we are running from.
    if len(sys.argv) == 1:
        log.error("This script needs to be executed from the tank command!")
        sys.exit(1)
    # the location of the actual tank core installation
    install_root = sys.argv[1]

    # pass the rest of the args into our checker
    cmd_line = sys.argv[2:] 

    # check if there is a --debug flag anywhere in the args list.
    # in that case turn on debug logging and remove the flag
    if "--debug" in cmd_line:
        log.setLevel(logging.DEBUG)
        log.debug("")
        log.debug("Running with debug output enabled.")
        log.debug("")
    cmd_line = [arg for arg in cmd_line if arg != "--debug"]
    
    # help requested?
    for x in cmd_line:
        if x == "--help" or x == "-h":
            exit_code = show_help(log)
            sys.exit(exit_code)
    
    # also we are passing the pipeline config 
    # at the back of the args as --pc=foo
    if len(cmd_line) > 0 and cmd_line[-1].startswith("--pc="):
        pipeline_config_root = cmd_line[-1][5:] 
    else:
        # now PC parameter passed. But it could be that we are using a localized core
        # meaning that the core is contained inside the project itself. In that case,
        # the install root is the same as the pipeline config root. We can check this my
        # looking for a file which exists in every project.
        templates_file = os.path.join(install_root, "config", "core", "templates.yml")
        if os.path.exists(templates_file):
            # looks like our code resides inside a project!
            log.debug("Found file %s - means we have a localized core!" % templates_file)
            pipeline_config_root = install_root
        else:
            pipeline_config_root = None
        
    # and strip out the --pc args
    cmd_line = [arg for arg in cmd_line if not arg.startswith("--pc=")]

    log.debug("Full command line passed: %s" % str(sys.argv))
    log.debug("")
    log.debug("")
    log.debug("Code install root: %s" % install_root)
    log.debug("Pipeline Config Root: %s" % pipeline_config_root)
    log.debug("")
    log.debug("")

    exit_code = 1
    try:

        if len(cmd_line) == 0:
            # > tank, no arguments
            # engine mode, using CWD
            exit_code = run_engine_cmd(log, 
                                       install_root, 
                                       pipeline_config_root, 
                                       [os.getcwd()], 
                                       None,
                                       True,
                                       [])
                     
        elif cmd_line[0] in CORE_PROJECT_COMMANDS:
            exit_code = run_core_project_command(log, 
                                                 install_root,
                                                 pipeline_config_root, 
                                                 cmd_line[0], 
                                                 cmd_line[1:])
        
        elif cmd_line[0] in CORE_NON_PROJECT_COMMANDS:
            exit_code = run_core_non_project_command(log, 
                                                     install_root,
                                                     pipeline_config_root, 
                                                     cmd_line[0], 
                                                     cmd_line[1:])
            
        else:
            # these choices remain:
            #
            # > tank command_name
            
            # > tank /path command_name [params]
            # > tank /path [params]
            
            # > tank Shot 123 command_name [params]
            # > tank Shot foo command_name [params]
            # > tank Shot 123
            # > tank Shot foo
            
            using_cwd = False
            ctx_list = []
            cmd_args = []
            
            if len(cmd_line) == 1:
                # tank /path
                # tank command
                if ("/" in cmd_line[0]) or ("\\" in cmd_line[0]):
                    # tank /foo/bar
                    ctx_list = [ cmd_line[0] ]
                    cmd_name = None
                else:
                    # tank command_name
                    cmd_name = cmd_line[0]
                    ctx_list = [ os.getcwd() ] # path
                    using_cwd = True
            
            elif len(cmd_line) == 2:
                # tank Shot 123
                # tank /path command_name
                # tank command_name param1
                if ("/" in cmd_line[0]) or ("\\" in cmd_line[0]):
                    # tank /foo/bar command_name
                    ctx_list = [ cmd_line[0] ]
                    cmd_name = cmd_line[1]
                elif cmd_line[0] in SHOTGUN_ENTITY_TYPES:
                    # tank Shot 123
                    cmd_name = None
                    ctx_list = [ cmd_line[0], cmd_line[1] ]                    
                else:
                    # tank command_name param1
                    cmd_name = cmd_line[0]
                    cmd_args = [ cmd_line[1] ]
                    ctx_list = [ os.getcwd() ] # path
                
            elif len(cmd_line) > 2:
                # tank Shot 123 command_name param1 param2 param3 ...
                # tank /path command param1 param2 param3 ...
                # tank command param1 param2 param3 ...

                if ("/" in cmd_line[0]) or ("\\" in cmd_line[0]):
                    # tank /foo/bar command_name param1
                    ctx_list = [ cmd_line[0] ]
                    cmd_name = cmd_line[1]
                    cmd_args = cmd_line[2:]
                elif cmd_line[0] in SHOTGUN_ENTITY_TYPES:
                    # tank Shot 123 command_name
                    cmd_name = cmd_line[2]
                    ctx_list = [ cmd_line[0], cmd_line[1] ]
                    cmd_args = cmd_line[3:]
                else:
                    # tank command_name param1 param2
                    cmd_name = cmd_line[0]
                    cmd_args = cmd_line[1:]
                    ctx_list = [ os.getcwd() ] # path
                

            exit_code = run_engine_cmd(log, 
                                       install_root, 
                                       pipeline_config_root, 
                                       ctx_list, 
                                       cmd_name,
                                       using_cwd,
                                       cmd_args)

    except TankError, e:
        # one line report
        log.info("")
        log.error(str(e))
        log.info("")
        log.info("tank command quick overview:")
        log.info("- To see a list of apps for a shot, run 'tank Shot XYZ'")
        log.info("- To check for updates, run 'tank updates' or 'tank core'.")
        log.info("- To install new things run 'tank install_app' or install_engine.")
        log.info("- To create folders for a shot, run 'tank folders Shot XYZ'.")
        log.info("- To set up a new project, run 'tank setup_project'.")
        log.info("")
        log.info("For more information try tank --help.")
        log.info("")
        exit_code = 5
        
    except KeyboardInterrupt, e:
        log.info("")
        log.info("Exiting.")
        exit_code = 6
    
    except Exception, e:
        # call stack
        log.info("")
        log.exception("An exception was reported: %s" % e)
        log.info("")                
        exit_code = 7
    
    log.debug("Exiting with exit code %s" % exit_code)
    sys.exit(exit_code)
