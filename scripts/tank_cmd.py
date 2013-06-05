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
from tank.deploy import setup_project
from tank.deploy import validate_config
from tank.deploy import administrator
from tank.deploy import core_api_admin
from tank.deploy import env_admin
from tank.deploy import tank_command
from tank.deploy.tank_commands.action_base import Action
from tank import pipelineconfig
from tank.util import shotgun
from tank.platform import engine
from tank import folder




###############################################################################################
# Constants

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

SHOTGUN_ENTITY_TYPES.extend(["CustomEntity%02d"%x for x in range(1, 31)])
SHOTGUN_ENTITY_TYPES.extend(["CustomNonProjectEntity%02d"%x for x in range(1, 16)])
SHOTGUN_ENTITY_TYPES.extend(["CustomThreadedEntity%02d"%x for x in range(1, 6)])

###############################################################################################
# Helpers and General Stuff

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
                # before converting, make sure the record is a string, sometimes
                # people pass in all sorts of crap into the logger
                message_str = str(record.msg)
                message = "<b>%s:</b> %s" % (record.levelname, cgi.escape(message_str))
            else:
                # info logging allows html chars to be passed so no cgi encode
                message = str(record.msg)

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

Show what commands are available for Shot ABC123 in project Flash
(In case you have several projects with a Shot ABC123)
> tank Shot Flash:ABC123

Show a list of all shots in Shotgun containing the phrase ABC
> tank Shot ABC

Launch maya for your current path (assuming this command exists):
> tank launch_maya

Launch maya for a Shot in Shotgun:
> tank Shot ABC123 launch_maya

Launch maya for a Task in Shotgun using an id:
> tank Task 234 launch_maya

Launch maya for a folder:
> tank /studio/proj_xyz/shots/ABC123 launch_maya

"""
    for x in info.split("\n"):
        log.info(x)




###############################################################################################
# Shotgun Actions Management

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


def shotgun_cache_actions(log, install_root, pipeline_config_root, args):
    """
    Executes the special shotgun cache actions command
    """

    # we are talking to shotgun! First of all, make sure we switch on our html style logging
    log.handlers[0].formatter.enable_html_mode()

    log.debug("Running shotgun_cache_actions command")
    log.debug("Arguments passed: %s" % args)

    try:
        tk = tank.tank_from_path(pipeline_config_root)
        # attach our logger to the tank instance
        # this will be detected by the shotgun and shell engines
        # and used.
        tk.log = log
    except TankError, e:
        raise TankError("Could not instantiate a Tank API Object! Details: %s" % e )

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


def shotgun_run_action(log, install_root, pipeline_config_root, args):
    """
    Executes the special shotgun run action command from inside of shotgun
    """

    # we are talking to shotgun! First of all, make sure we switch on our html style logging
    log.handlers[0].formatter.enable_html_mode()

    log.debug("Running shotgun_run_action command")
    log.debug("Arguments passed: %s" % args)

    try:
        tk = tank.tank_from_path(pipeline_config_root)
        # attach our logger to the tank instance
        # this will be detected by the shotgun and shell engines
        # and used.
        tk.log = log
    except TankError, e:
        raise TankError("Could not instantiate a Tank API Object! Details: %s" % e )

    # params: action_name, entity_type, entity_ids
    if len(args) != 3:
        raise TankError("Invalid arguments! Pass action_name, entity_type, comma_separated_entity_ids")

    action_name = args[0]
    entity_type = args[1]
    entity_ids_str = args[2].split(",")
    entity_ids = [int(x) for x in entity_ids_str]

    if action_name == "__clone_pc":
        # special data passed in entity_type: USER_ID:NAME:LINUX_PATH:MAC_PATH:WINDOWS_PATH
        user_id = int(entity_type.split(":")[0])
        new_name = entity_type.split(":")[1]
        new_path_linux = entity_type.split(":")[2]
        new_path_mac = entity_type.split(":")[3]
        # note - since the windows path may contain colons, assume all items
        # past the 4th chunk in the command is part of the windows path...
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






###############################################################################################
# Shell Actions Management

def _list_commands(log, tk, ctx):
    """
    Output a list of commands given the current context etc
    """

    # get all the action objets (commands) suitable for the current context
    (aa, engine) = tank_command.get_actions(log, tk, ctx)

    log.info("")
    log.info("The following commands are available:")

    # group by category
    by_category = {}
    for x in aa:
        if x.category not in by_category:
            by_category[x.category] = []
        by_category[x.category].append(x)

    num_engine_commands = 0
    for cat in sorted(by_category.keys()):
        log.info("")
        log.info("=" * 50)
        log.info("%s Commands" % cat)
        log.info("=" * 50)
        log.info("")
        for cmd in by_category[cat]:
            log.info(cmd.name)
            log.info("-" * len(cmd.name))
            log.info(cmd.description)
            log.info("")
            # keep track of number of engine commands
            if cmd.mode == Action.ENGINE:
                num_engine_commands += 1



    if num_engine_commands == 0:
        # not a fully populated setup - so display some interactive help!
        log.info("")
        log.info("=" * 50)
        log.info("Didn't find what you were looking for?")
        log.info("=" * 50)
        log.info("")

        if tk is None:
            # we have nothing.
            log.info("You have launched the Tank command without a Project. This means that you "
                     "are only getting a small number of global system commands in the list of "
                     "commands. Try pointing the tank command to a project location, for example: ")
            log.info("")
            log.info("> tank Project XYZ")
            log.info("> tank Shot ABC123")
            log.info("> tank Asset ALL")
            log.info("> tank /mnt/projects/my_project/shots/ABC123")
            log.info("")

        elif ctx is None:
            # we have a project but no context.
            log.info("You have launched the Tank command but not pointed it at a specific "
                     "work area. You are running tank from the configuration found in "
                     "'%s' but no specific asset or shot was selected so only a generic list "
                     "of commands will be displayed. Try pointing the tank command to a more "
                     "specific location, for example: " % tk.pipeline_configuration.get_path())
            log.info("")
            log.info("> tank Shot ABC123")
            log.info("> tank Asset ALL")
            log.info("> tank /mnt/projects/my_project/shots/ABC123")
            log.info("")

        else:
            # we have a context but no engine!
            # no engine may be because of a couple of reasons:
            # 1. no environment was found for the context
            # 2. no shell engine was installed
            # 3. no apps are installed for the shell engine

            env = tank.platform.engine.get_environment_from_context(tk, ctx)
            if env is None:
                # no environment for context
                log.info("Your current context ('%s') does not have a matching environment in Tank. "
                         "An environment is a part of the configuration and is used to define what "
                         "tools are available in a certain part of the pipeline. For example, you "
                         "may have a Shot and and Asset environment, defining the different tools "
                         "needed for asset work and shot work. Try navigating to a more specific "
                         "part of your project setup, or contact support if you have further "
                         "questions." % ctx)


            elif tank.platform.constants.SHELL_ENGINE not in env.get_engines():
                # no shell engine installed
                log.info("Looks like the environment configuration '%s', which is associated "
                         "with the current context (%s), does not have a shell engine "
                         "installed. The shell engine is necessary if you want to run apps using "
                         "the tank command. You can install it by running the install_engine "
                         "command." % (env.disk_location, ctx))

            else:
                # number engine commands is zero
                log.info("Looks like you don't have any apps installed that can run in the shell "
                         "engine! Try installing apps using the install_app command or start a new "
                         "project based on the latest Tank default starter configuration if you want "
                         "to get a working example of how the shell engine can be configured.")


    log.info("")
    log.info("")


def _preprocess_projects(log, sg, entity_search_token, constrain_by_project_id):
    """
    Returns project constraint data given a search token and a filter.

    If the token is on the form "abc", there is no project prefix.
    However, if the project is on the form abc:XYZ, search for projects matching
    abc.

    if we are constraining by project, project prefix is not valid.
    """

    if ":" in entity_search_token:
        proj_token = entity_search_token.split(":")[0]
        entity_token = ":".join(entity_search_token.split(":")[1:])
    else:
        proj_token = None
        entity_token = entity_search_token

    if constrain_by_project_id:
        # find project details
        proj_constraint = sg.find_one("Project", [["id", "is", constrain_by_project_id]], ["name"])
    else:
        proj_constraint = None

    if proj_token:
        # find wild card projects
        projs_from_prefix = sg.find("Project", [["name", "contains", proj_token]], ["name"])
        if len(projs_from_prefix) == 0:
            raise TankError("No Shotgun projects found containing the phrase '%s' in their name!" % proj_token)
    else:
        projs_from_prefix = []

    # if we are running a local tank command, no project prefixes unless it happens to be
    # matching only that project!
    if proj_constraint:
        log.info("You are running a tank command associated with Shotgun Project '%s'. "
                 "Only items associated with this project will be considered." % proj_constraint.get("name") )
        if len(projs_from_prefix) > 0:
            log.warning("Your specific project filters will be ignored.")

        projs_from_prefix = [proj_constraint]

    else:
        # studio command!
        if len(projs_from_prefix) == 1:
            log.info("")
            log.info("Only items from project %s will be considered." % projs_from_prefix[0].get("name"))

        elif len(projs_from_prefix) > 1:
            proj_names = [x.get("name") for x in projs_from_prefix]
            log.info("")
            log.info("Will search in the following projects: %s" % ", ".join(proj_names))

    if len(projs_from_prefix) == 0:
        log.info("Will search across all Shotgun Projects.")

    return (entity_token, projs_from_prefix)

def _resolve_shotgun_entity(log, entity_type, entity_search_token, constrain_by_project_id):
    """
    Resolves a Shotgun context when someone specifies tank Shot ABC.
    Will present multiple matches if there isn't a unique match

    returns an entity_id
    """

    sg = shotgun.create_sg_connection()

    name_field = "code"
    if entity_type == "Project":
        name_field = "name"
    elif entity_type == "Task":
        name_field = "content"
    elif entity_type == "HumanUser":
        name_field = "login"

    # if entity_search_token is on the form ghosts:P01, limit by project
    (entity_only_search_token, projs) = _preprocess_projects(log, sg, entity_search_token, constrain_by_project_id)

    try:
        shotgun_filters = []

        if entity_only_search_token != "ALL":
            shotgun_filters.append([name_field, "contains", entity_only_search_token])

        if len(projs) > 0:
            # append project constraint! Note the funny filter syntax
            proj_filter = ["project", "in"]
            proj_filter.extend(projs)
            shotgun_filters.append(proj_filter)

        entities = sg.find(entity_type,
                           shotgun_filters,
                           [name_field, "description", "entity", "link", "project"])
    except Exception, e:
        raise TankError("An error occurred when searching in Shotgun: %s" % e)

    if len(entities) == 0:
        log.info("")
        log.info("Could not find a %s with a name containing '%s' in Shotgun!" % (entity_type, entity_only_search_token))
        raise TankError("Try searching for something else. Alternatively, specify ALL in order to see all %ss." % entity_type)

    elif len(entities) == 1:
        # single match yay
        entity = entities[0]

        # make sure there is a project associated with this entity!
        if entity_type != "Project":
            if entity.get("project") is None:
                raise TankError("Found %s %s however this item is not associated with "
                                "a Project!" % (entity_type, entity[name_field]))

            log.info("- Found %s %s (Project '%s')" % (entity_type,
                                                     entity[name_field],
                                                     entity["project"]["name"]))

        else:
            # project case
            log.info("- Found %s %s" % (entity_type, entity[name_field]))


        return entity["id"]

    else:

        # More than one item matching Shot 'P':
        #
        # [860] Shot P12 (The ghosts of Pere Lachaise)
        #       There is no description for this item.
        #
        # [861] Shot P13 (The ghosts of Pere Lachaise)
        #       There is no description for this item.
        #
        # [862] Shot P01 (The ghosts of Pere Lachaise)
        #       Camera starts with a wide view of Paris then cranes down to see...


        log.info("")
        log.info("More than one item matching your input:" )
        log.info("")
        for x in entities:

            chunks = []

            chunks.append(" [%d]" % x["id"])
            id_chunk_len = len(chunks[0]) # used for description formatter

            chunks.append(" %s %s" % (entity_type, x[name_field]))

            if x.get("project"):
                chunks.append(" (%s)" % x.get("project").get("name"))

            if x.get("entity"):
                chunks.append( " (%s %s)" % (x.get("entity").get("type"),
                                             x.get("entity").get("name")))

            if x.get("link"):
                chunks.append( " (%s %s)" % (x.get("link").get("type"),
                                             x.get("link").get("name")))

            log.info("".join(chunks))


            # display description and chop it off so that is never longer than a single line
            desc = x.get("description")
            if desc is None:
                desc = "There is no description for this item."

            # add spaces to push the desc to align with [id]
            desc = (" " * id_chunk_len) + " " + desc

            chars_available = 70 # description max len is 70

            # clever regex to chop on word boundaries
            chopped_desc = re.match(r'(.{,%d})(\W|$)' % chars_available, desc).group(1)
            if len(chopped_desc) < len(desc):
                chopped_desc += "..."

            log.info(chopped_desc)

            log.info("")


        log.info("More than one item matched your search phrase '%s'! "
                 "Please enter a more specific search phrase in order to narrow it down "
                 "to a single match. "
                 "If there are items with the same name, you can use the [id] field displayed "
                 "in order to refer to a particular object." % entity_only_search_token)

        if len(projs) == 0:
            # not using any project filters
            log.info("")
            log.info("If you want to search on items from a particular project, you can either "
                     "run the tank command from that particular project or prefix your search "
                     "string with a project name. For example, if you want to only see matches "
                     "from projects containing the phrase VFX, search for '%s VFX:%s'" % (entity_type, entity_only_search_token))

        log.info("")
        raise TankError("Please try again with a more specific search!")






def run_engine_cmd(log, install_root, pipeline_config_root, context_items, command, using_cwd, args):
    """
    Launches an engine and potentially executes a command.

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
    log.debug("Context items: %s" % str(context_items))
    log.debug("Command: %s" % command)
    log.debug("Command Arguments: %s" % args)
    log.debug("Code Location Root: %s" % install_root)
    log.debug("Tank Command Location: %s" % pipeline_config_root)
    log.debug("Location of this script (__file__): %s" % os.path.abspath(__file__))

    log.info("")
    log.info("Welcome to Tank!")

    # Now create a tk instance and a context if possible

    if len(context_items) == 1:

        ctx_path = context_items[0]

        if using_cwd:
            log.info("Starting Tank for your current directory '%s'" % ctx_path)

        # context str is a path
        if pipeline_config_root is not None:
            # we are running a project specific tank command
            tk =  tank.tank_from_path(pipeline_config_root)

        else:
            # we are running a studio wide command
            try:
                tk = tank.tank_from_path(ctx_path)
            except TankError, e:
                # this path was not valid. That's ok - we just wont have a tank instance
                # when we run our commands later. This may be if we for example have
                # just run tank setup_project from any random folder
                log.debug("Instantiating Tank raised: %s" % e)
                tk = None

        # now try to extract a context
        ctx = None
        if tk is not None:
            ctx = tk.context_from_path(ctx_path)

    elif context_items[1].isdigit():

        # shotgun entity type and entity id!
        entity_type = context_items[0]
        entity_id = int(context_items[1])

        # note - tank from path method will validate that we are launching
        # from the right tank command etc.
        tk = tank.tank_from_entity(entity_type, entity_id)

        ctx = tk.context_from_entity(entity_type, entity_id)

    elif pipeline_config_root is not None:

        # shotgun entity type and entity name and we are running a local tank command
        tk =  tank.tank_from_path(pipeline_config_root)

        # now parse and resolve the entity name string
        entity_type = context_items[0]
        entity_search_token = context_items[1]
        project_id = tk.pipeline_configuration.get_project_id()
        entity_id = _resolve_shotgun_entity(log, entity_type, entity_search_token, project_id)
        ctx = tk.context_from_entity(entity_type, entity_id)

    else:

        # shotgun entity type and entity name and we are running a global tank command

        # now parse and resolve the entity name string
        entity_type = context_items[0]
        entity_search_token = context_items[1]
        entity_id = _resolve_shotgun_entity(log, entity_type, entity_search_token, None)
        tk = tank.tank_from_entity(entity_type, entity_id)
        ctx = tk.context_from_entity(entity_type, entity_id)

    log.debug("Tank API and Context resolve complete.")
    log.debug("Tank API: %s" % tk)
    log.debug("Context: %s" % ctx)

    if tk is not None:
        if pipeline_config_root is None:
            # generic tank command - so indicate which config was picked
            log.info("- Starting Tank %s using configuration %s." % (tk.version, tk.pipeline_configuration.get_path()))
        else:
            log.info("- Starting Tank %s." % tk.version)

        # attach our logger to the tank instance
        # this will be detected by the shotgun and shell engines and used.
        tk.log = log

    if ctx is not None:
        log.info("- Setting the Context to %s." % ctx)

    if command is None:
        return _list_commands(log, tk, ctx)
    else:
        return tank_command.run_action(install_root, pipeline_config_root, log, tk, ctx, command, args)





if __name__ == "__main__":

    # set up logging channel for this script
    logger = logging.getLogger("tank.setup_project")
    logger.setLevel(logging.INFO)

    ch = logging.StreamHandler(sys.stdout)
    formatter = AltCustomFormatter()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # the first argument is always the path to the code root
    # we are running from.
    if len(sys.argv) == 1:
        logger.error("This script needs to be executed from the tank command!")
        sys.exit(1)
    # the location of the actual tank core installation
    install_root = sys.argv[1]

    # pass the rest of the args into our checker
    cmd_line = sys.argv[2:]

    # check if there is a --debug flag anywhere in the args list.
    # in that case turn on debug logging and remove the flag
    if "--debug" in cmd_line:
        logger.setLevel(logging.DEBUG)
        logger.debug("")
        logger.debug("Running with debug output enabled.")
        logger.debug("")
    cmd_line = [arg for arg in cmd_line if arg != "--debug"]

    # help requested?
    for x in cmd_line:
        if x == "--help" or x == "-h":
            exit_code = show_help(logger)
            sys.exit(exit_code)

    # also we are passing the pipeline config
    # at the back of the args as --pc=foo
    if len(cmd_line) > 0 and cmd_line[-1].startswith("--pc="):
        pipeline_config_root = cmd_line[-1][5:]
    else:
        # no PC parameter passed. But it could be that we are using a localized core
        # meaning that the core is contained inside the project itself. In that case,
        # the install root is the same as the pipeline config root. We can check this my
        # looking for a file which exists in every project.
        templates_file = os.path.join(install_root, "config", "core", "templates.yml")
        if os.path.exists(templates_file):
            # looks like our code resides inside a project!
            logger.debug("Found file %s - means we have a localized core!" % templates_file)
            pipeline_config_root = install_root
        else:
            pipeline_config_root = None

    # and strip out the --pc args
    cmd_line = [arg for arg in cmd_line if not arg.startswith("--pc=")]

    logger.debug("Full command line passed: %s" % str(sys.argv))
    logger.debug("")
    logger.debug("")
    logger.debug("Code install root: %s" % install_root)
    logger.debug("Pipeline Config Root: %s" % pipeline_config_root)
    logger.debug("")
    logger.debug("")

    exit_code = 1
    try:

        if len(cmd_line) == 0:
            # > tank, no arguments
            # engine mode, using CWD
            exit_code = run_engine_cmd(logger,
                                       install_root,
                                       pipeline_config_root,
                                       [os.getcwd()],
                                       None,
                                       True,
                                       [])

        # special case when we are called from shotgun
        elif cmd_line[0] == "shotgun_run_action":
            exit_code = shotgun_run_action(logger, install_root, pipeline_config_root, cmd_line[1:])

        # special case when we are called from shotgun
        elif cmd_line[0] == "shotgun_cache_actions":
            exit_code = shotgun_cache_actions(logger, install_root, pipeline_config_root, cmd_line[1:])

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


            exit_code = run_engine_cmd(logger,
                                       install_root,
                                       pipeline_config_root,
                                       ctx_list,
                                       cmd_name,
                                       using_cwd,
                                       cmd_args)

    except TankError, e:
        # one line report
        logger.info("")
        logger.error(str(e))
        logger.info("")
        exit_code = 5

    except KeyboardInterrupt, e:
        logger.info("")
        logger.info("Exiting.")
        exit_code = 6

    except Exception, e:
        # call stack
        logger.info("")
        logger.exception("A general error was reported: %s" % e)
        logger.info("")
        exit_code = 7

    logger.debug("Exiting with exit code %s" % exit_code)
    sys.exit(exit_code)
