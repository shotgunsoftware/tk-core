# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sys
import os
import cgi
import re
import logging
import tank
import textwrap
import datetime
from tank import TankError, TankAuthenticationError
from tank.deploy.tank_commands.clone_configuration import clone_pipeline_configuration_html
from tank.deploy import tank_command
from tank.deploy.tank_commands.core_upgrade import TankCoreUpgrader
from tank.deploy.tank_commands.action_base import Action
from tank.util import shotgun, DefaultsManager
from tank_vendor.shotgun_authentication import ShotgunAuthenticator, AuthenticationModuleError
from tank.platform import engine
from tank import pipelineconfig_utils




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
                        'PublishedFile', 'PublishedFileType', 'PublishedFileDependency',
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
            if record.levelno in (logging.WARNING, logging.ERROR, logging.CRITICAL):
                record.msg = '%s: %s' % (record.levelname, record.msg)

            if record.levelno == logging.DEBUG:
                # time stamps in debug logging!
                record.msg = 'DEBUG [%s %s]: %s' % (datetime.datetime.now().strftime("%H:%M:%S"),
                                                    record.msecs,
                                                    record.msg)

            if "Code Traceback" not in record.msg:
                # do not wrap exceptions
                lines = []
                for x in textwrap.wrap(record.msg, width=78, break_long_words=False, break_on_hyphens=False):
                    lines.append(x)
                record.msg = "\n".join(lines)

        self._num_items += 1
        return logging.Formatter.format(self, record)


def show_help(log):

    info = """
Welcome to the Shotgun pipeline toolkit!

This command lets you control Toolkit from a shell. You can start apps and
engines via the Tank command. You can also run various admin commands.


General options and info
----------------------------------------------
- To show this help, add a -h or --help flag.
- To display verbose debug, add a --debug flag.


Executing Commands
----------------------------------------------
Syntax: tank [context] command [args]

 - Context is a location on disk where you want the command to operate.
   It can also be a Shotgun Entity on the form Type id or Type name describing
   the object you want to operate on. If you leave this out, the command
   will use your current working directory as the context.

 - Command is the engine command to execute. If you leave this out then the
   available commands will be listed.

Examples:

Show what commands are available for the current directory:
> tank

Show what commands are available for Shot ABC123
> tank Shot ABC123

Show what commands are available for Shot ABC123 in project Flash
(In case you have several projects with a Shot ABC123. Note that this
 only works when running from a tank studio command)
> tank Shot Flash:ABC123

Show a list of all shots in Shotgun containing the phrase ABC
> tank Shot ABC

Launch maya for your current path (assuming this command exists):
> tank launch_maya

Launch maya for a Shot in Shotgun:
> tank Shot ABC123 launch_maya

Launch maya for a Task in Shotgun using an id:
> tank Task @234 launch_maya

Launch maya for a folder:
> tank /studio/proj_xyz/shots/ABC123 launch_maya

Log out of the current user (no need for a contex):
> tank logout

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

    cache_path = os.path.join(tk.pipeline_configuration.get_shotgun_menu_cache_location(), cache_file_name)

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
        # Note that we are using binary form here to ensure that the line
        # endings are written out consistently on all different OSes
        # otherwise with wt mode, \n on windows will be turned into \n\r
        # which is not interpreted correctly by the jacascript code.
        f = open(cache_path, "wb")
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


def shotgun_cache_actions(log, pipeline_config_root, args):
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
        raise TankError("Could not instantiate an Sgtk API Object! Details: %s" % e )

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


def shotgun_run_action(log, install_root, pipeline_config_root, is_localized, args):
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
        raise TankError("Could not instantiate an Sgtk API Object! Details: %s" % e )

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
        clone_pipeline_configuration_html(log,
                                          tk,
                                          pc_entity_id,
                                          user_id,
                                          new_name,
                                          new_path_linux,
                                          new_path_mac,
                                          new_path_windows,
                                          is_localized)

    elif action_name == "__core_info":

        code_css_block = "display: block; padding: 0.5em 1em; border: 1px solid #bebab0; background: #faf8f0;"

        # create an upgrader instance that we can query if the install is up to date
        installer = TankCoreUpgrader(install_root, log)

        cv = installer.get_current_version_number()
        lv = installer.get_latest_version_number()
        log.info("You are currently running version %s of the Shotgun Pipeline Toolkit." % cv)

        if not is_localized:
            log.info("")
            log.info("Your core API is located in <code>%s</code> and is shared with other "
                     "projects." % install_root)

        log.info("")

        status = installer.get_update_status()
        req_sg = installer.get_required_sg_version_for_upgrade()

        if status == TankCoreUpgrader.UP_TO_DATE:
            log.info("<b>You are up to date! There is no need to update the Toolkit Core API at this time!</b>")

        elif status == TankCoreUpgrader.UPGRADE_BLOCKED_BY_SG:
            log.warning("<b>A new version (%s) of the core API is available however "
                        "it requires a more recent version (%s) of Shotgun!</b>" % (lv, req_sg))

        elif status == TankCoreUpgrader.UPGRADE_POSSIBLE:

            (summary, url) = installer.get_release_notes()

            log.info("<b>A new version of the Toolkit API (%s) is available!</b>" % lv)
            log.info("")
            log.info("<b>Change Summary:</b> %s <a href='%s' target=_new>"
                     "Click for detailed Release Notes</a>" % (summary, url))
            log.info("")
            log.info("In order to upgrade, execute the following command in a shell:")
            log.info("")

            if sys.platform == "win32":
                tank_cmd = os.path.join(install_root, "tank.bat")
            else:
                tank_cmd = os.path.join(install_root, "tank")

            log.info("<code style='%s'>%s core</code>" % (code_css_block, tank_cmd))

            log.info("")

        else:
            raise TankError("Unknown Upgrade state!")


    elif action_name == "__upgrade_check":

        # special built in command that simply tells the user to run the tank command

        code_css_block = "display: block; padding: 0.5em 1em; border: 1px solid #bebab0; background: #faf8f0;"

        log.info("In order to check if your installed apps and engines are up to date, "
                 "you can run the following command in a console:")

        log.info("")

        if sys.platform == "win32":
            tank_cmd = os.path.join(pipeline_config_root, "tank.bat")
        else:
            tank_cmd = os.path.join(pipeline_config_root, "tank")

        log.info("<code style='%s'>%s updates</code>" % (code_css_block, tank_cmd))

        log.info("")

    else:
        _run_shotgun_command(log, tk, action_name, entity_type, entity_ids)






###############################################################################################
# Shell Actions Management

def _get_sg_name_field(entity_type):
    """
    Returns the standard Shotgun name field given an entity type.
    
    :param entity_type: shotgun entity type
    :returns: name field as string
    """
    name_field = "code"
    if entity_type == "Project":
        name_field = "name"
    elif entity_type == "Task":
        name_field = "content"
    elif entity_type == "HumanUser":
        name_field = "login"
    return name_field

def _resolve_shotgun_pattern(log, entity_type, name_pattern):
    """
    Resolve a pattern given an entity. Search the 'name' field
    for an entity. For most types, this is the code field.
    Raise exceptions unless there is a single matching item.
    
    :param entity_type: Entity type to search
    :param name_pattern: Name pattern to search for
    :returns: (entity id, name)
    """

    name_field = _get_sg_name_field(entity_type)
    
    sg = shotgun.get_sg_connection()
    
    log.debug("Shotgun: find(%s, %s contains %s)" % (entity_type, name_field, name_pattern) )
    data = sg.find(entity_type, [[name_field, "contains", name_pattern]], [name_field])
    log.debug("Got data: %r" % data)
    
    if len(data) == 0:
        raise TankError("No Shotgun %s matching the pattern '%s'!" % (entity_type, name_pattern))
    
    elif len(data) > 1:
        names = ["'%s'" % x[name_field] for x in data]
        raise TankError("More than one %s matching pattern '%s'. Matching items are %s. " 
                        "Please be more specific." % (entity_type, name_pattern, ", ".join(names)))
    
    # got a single item 
    return (data[0]["id"], data[0][name_field])



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

    # Add Login category manually, since they are not commands per-se since they are run before the
    # engine is initialized.

    by_category.setdefault("Login", []).append(
        Action("logout", "unused", "Log out of the current user (no need for a contex).", "Login")
    )

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
                log.info("Your current context ('%s') does not have a matching Sgtk Environment. "
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
                         "project based on the latest Sgtk default starter configuration if you want "
                         "to get a working example of how the shell engine can be configured.")


    log.info("")
    log.info("")







def _resolve_shotgun_entity(log, entity_type, entity_search_token, constrain_by_project_id):
    """
    Resolves a Shotgun context when someone specifies tank Shot ABC.
    Will display multiple matches to the logger if there isn't a unique match.

    :param entity_type: Entity type to resolve
    :param entity_search_token: Partial name to search for
    :param constrain_by_project_id: Project id to constrain the search to. 
                                    When this is None, all projects will be considered.
    :returns: a matching entity_id
    """

    sg = shotgun.get_sg_connection()
    name_field = _get_sg_name_field(entity_type)

    try:
        # build up filters
        shotgun_filters = []

        if entity_search_token != "ALL":
            shotgun_filters.append([name_field, "contains", entity_search_token])

        if constrain_by_project_id:
            # append project constraint
            shotgun_filters.append(["project", "is" , {"type": "Project", "id": constrain_by_project_id}])

        log.debug("Shotgun: find(%s, %s)" % (entity_type, shotgun_filters))
        entities = sg.find(entity_type,
                           shotgun_filters,
                           [name_field, "description", "entity", "link", "project"])
        log.debug("Got data: %r" % entities)
    except Exception, e:
        raise TankError("An error occurred when searching in Shotgun: %s" % e)

    selected_entity = None

    if len(entities) == 0:
        log.info("")
        log.info("Could not find a %s with a name containing '%s' in Shotgun!" % (entity_type, entity_search_token))
        raise TankError("Try searching for something else. "
                        "Alternatively, specify ALL in order to see all %ss." % entity_type)


    elif [ x[name_field] for x in entities ].count(entity_search_token) == 1:
        # multiple matches but one matches the search term exactly!!
        # find which one:
        for x in entities:
            if x[name_field] == entity_search_token:
                selected_entity = x

    elif len(entities) == 1:
        # single match yay
        selected_entity = entities[0]

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

            chunks.append(" [@%d]" % x["id"])
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


        if entity_search_token != "ALL":
            # don't display this helpful hint if they have used the special ALL keyword
            log.info("More than one item matched your search phrase '%s'! "
                     "Please enter a more specific search phrase in order to narrow it down "
                     "to a single match. If there are several items with the same name, "
                     "you can use the @id field displayed to specify a particular "
                     "object (e.g. '%s @123')." % (entity_search_token, entity_type))

        if constrain_by_project_id is None:
            # not using any project filters
            log.info("")
            log.info("If you want to search on items from a particular project, you can either "
                     "run the tank command from that particular project or prefix your search "
                     "string with a project name. For example, if you want to only see matches "
                     "from a project named VFX, search for '%s VFX:%s'" % (entity_type, entity_search_token))

        log.info("")
        raise TankError("Please try again with a more specific search!")



    # make sure there is a project associated with this entity!
    # selected_entity now has an entity populated in it.
    if entity_type != "Project":
        if selected_entity.get("project") is None:
            raise TankError("Found %s %s however this item is not associated with "
                            "a Project!" % (entity_type, selected_entity[name_field]))

        log.info("- Found %s %s (Project '%s')" % (entity_type,
                                                 selected_entity[name_field],
                                                 selected_entity["project"]["name"]))

    else:
        # project case
        log.info("- Found %s %s" % (entity_type, selected_entity[name_field]))


    return selected_entity["id"]



def run_engine_cmd(log, pipeline_config_root, context_items, command, using_cwd, args):
    """
    Launches an engine and potentially executes a command.

    :param log: logger
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
    log.debug("Sgtk Pipeline Config Location: %s" % pipeline_config_root)
    log.debug("Location of this script (__file__): %s" % os.path.abspath(__file__))

    log.info("")

    log.info("Welcome to the Shotgun Pipeline Toolkit!")
    log.info("For documentation, see https://toolkit.shotgunsoftware.com")

    # Now create a tk instance and a context if possible
    ctx = None
    tk = None

    if len(context_items) == 1:
        # path mode: e.g. tank /foo/bar/baz
        # create a context given a path as the input

        ctx_path = context_items[0]

        if using_cwd:
            log.info("Starting Toolkit for your current path '%s'" % ctx_path)
        else:
            log.info("Starting toolkit for path '%s'" % ctx_path)

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
                log.debug("Instantiating Sgtk raised: %s" % e)

        if tk is not None:
            #
            # Right, there is a valid tk api handle, this means one of the following:
            #
            # - a project specific tank command guarantees a tk instance 
            #
            # - a studio level tank command which is targetting a path 
            #   which belongs to a toolkit project 
            # 
            # It is possible that someone has launched a project specific
            # tank command with a path which is outside the project.
            # In this case, initialize this to have the project context.   
            # We do this by attempting to construct a context and probing it
            
            ctx = tk.context_from_path(ctx_path)
            if ctx.project is None:
                # context could not be determined based on the path
                # revert back to the project context
                log.info("- The path is not associated with any Shotgun object.")
                log.info("- Falling back on default project settings.")
                project_id = tk.pipeline_configuration.get_project_id()
                ctx = tk.context_from_entity("Project", project_id)                

    else:
        # this is a shotgun syntax. e.g. 'tank Shot foo'
        # create a context given an entity and entity_id/entity_name
        entity_type = context_items[0]
        entity_search_token = context_items[1]

        if pipeline_config_root is not None and entity_type == "Project":
            # this is a per project tank command which is specifying the Project to run
            # the project is already implied by the location of the tank command
            raise TankError("You are executing a project specific tank command so there is "
                            "no need to specify a Project parameter! Try running just the "
                            "tank command with no parameters to see what options are available "
                            "on the project level. Alternatively, you can pass a Shotgun entity "
                            "(e.g. 'Shot abc123') or a path on disk to specify a particular "
                            "environment to see the available commands.")

        # now see if we are running a studio or a per project tank command
        if pipeline_config_root is not None:
            # running a per project command
            tk =  tank.tank_from_path(pipeline_config_root)
            project_id = tk.pipeline_configuration.get_project_id()
            studio_command_mode = False
                   
        else:
            # studio level command
            project_id = None
            studio_command_mode = True    
            
        # now resolve the given expression. For clarity, this is done as two separate branches
        # depending on if you are calling from a studio tank command or from a project tank command
        
        # the valid syntax here is
        # tank Entitytype name_expression
        # tank EntityType id   (fallback if there is no item with the given name)
        # tank EntityType @123 (explicit addressing by id)
        
        # special studio level only syntax
        # raises an error for project level command
        # tank Shot Project:xxx
        
        # first pass - remove a potential project prefix.
        # if someone passes a project prefix, ensure that the studio command is running
        # otherwise error out.
        
        # first output some info if we are running the project command
        if not studio_command_mode:
            log.info("- You are running a project specific tank command. Only items that are part "
                     "of this project will be considered.")

        # work out the project prefix logic    
        if ":" in entity_search_token:
            
            # we have an expression on the form tank EntityType project_name:name_expression
            # this is not valid for non-studio commands because these are already project scoped
            if not studio_command_mode:
                raise TankError("Invalid syntax! When you are running the tank command from "
                                "a project, you are already implicitly scoping your search by "
                                "that project. Please omit the project prefix from your syntax. "
                                "For more information, run tank --help")
            
            elif entity_type == "Project":
                # ok so we have a studio level command
                # but you cannot scope a project by another project
                raise TankError("Cannot scope a project with another project! For more information, "
                                "run tank --help")
        
            else:
                # studio level command and non-project entity.
                # pop off the project token from the entity search token
                proj_token = entity_search_token.split(":")[0]
                entity_search_token = ":".join(entity_search_token.split(":")[1:])
                
                # now try to resolve this project
                (project_id, project_name) = _resolve_shotgun_pattern(log, "Project", proj_token)
                log.info("- Searching in project '%s' only" % project_name)

            
        # now project prefix token has been removed from the path
        # we now have the following cases to consider
        # tank Entitytype name_expression
        # tank EntityType id   (fallback if there is no item with the given name)
        # tank EntityType @123 (explicit addressing by id)        
        
        run_expression_search = True
        
        if entity_search_token.isdigit():
            # the entity name is something like "123"
            # first look if there is an exact match for it. 
            # If not, assume it is an id.
            sg = shotgun.get_sg_connection()
            name_field = _get_sg_name_field(entity_type)

            # first try by name - e.g. a shot named "123"
            filters = [[name_field, "is", entity_search_token]]
            if project_id:
                # when running a per project tank command, make sure we 
                # filter out all other items in other projects.
                filters.append( ["project", "is", {"type": "Project", "id": project_id} ])
            
            log.debug("Shotgun: find(%s, %s)" % (entity_type, filters))
            data = sg.find(entity_type, filters, ["id", name_field])
            log.debug("Got data: %r" % data)
            
            if len(data) == 0:
                # no exact match. Assume the string is an id
                log.info("- Did not find a %s named '%s', will look for a %s with id %s "
                         "instead." % (entity_type, entity_search_token, entity_type, entity_search_token))
                entity_id = int(entity_search_token)
                
                # now we have our entity id, make sure we don't search for this as an expression 
                run_expression_search = False
                
        elif entity_search_token.startswith("@") and entity_search_token[1:].isdigit():
            # special syntax to ensure that you can unambiguously refer to ids
            # 'tank Shot @123' means that you specifically refer to a Shot with id 123,
            # not a shot named "123". This syntax is explicit and is also faster to evaluate
            entity_id = int(entity_search_token[1:])
            log.info("- Looking for a %s with id %d." % (entity_type, entity_id))
            log.debug("Direct @id syntax - will resolve entity id %d" % entity_id)
            # now we have our entity id, make sure we don't search for this as an expression 
            run_expression_search = False
            
        
        if run_expression_search:
            # use normal string based parse methods
            # we are now left with the following cases to resolve
            # tank Entitytype name_expression
            entity_id = _resolve_shotgun_entity(log, entity_type, entity_search_token, project_id)
            
        # now initialize toolkit and set up the context.  
        tk = tank.tank_from_entity(entity_type, entity_id)
        ctx = tk.context_from_entity(entity_type, entity_id)

    log.debug("Sgtk API and Context resolve complete.")
    log.debug("Sgtk API: %s" % tk)
    log.debug("Context: %s" % ctx)

    if tk is not None:
        log.info("- Using configuration '%s' and Core %s" % (tk.pipeline_configuration.get_name(), tk.version))
        # attach our logger to the tank instance
        # this will be detected by the shotgun and shell engines and used.
        tk.log = log

    if ctx is not None:
        log.info("- Setting the Context to %s." % ctx)

    if command is None:
        return _list_commands(log, tk, ctx)
    else:
        # pass over to the tank commands api - this will take over command execution,
        # setup the objects accordingly etc.
        return tank_command.run_action(log, tk, ctx, command, args)





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
    debug_mode = False
    if "--debug" in cmd_line:
        debug_mode = True
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

    # determine if we are running a localized core API.
    is_localized = pipelineconfig_utils.is_localized(install_root)

    # also we are passing the pipeline config
    # at the back of the args as --pc=foo
    if len(cmd_line) > 0 and cmd_line[-1].startswith("--pc="):
        pipeline_config_root = cmd_line[-1][5:]
    else:
        # no PC parameter passed. But it could be that we are using a localized core
        # meaning that the core is contained inside the project itself. In that case,
        # the install root is the same as the pipeline config root.
        if is_localized:
            logger.debug("Core API resides inside a (localized) pipeline configuration.")
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

        # If the user is trying to logout, try to do so
        if "logout" in cmd_line:
            sa = ShotgunAuthenticator(DefaultsManager())
            # Clear the saved user.
            user = sa.clear_saved_user()
            if user:
                logger.info("Succesfully logged out from %s." % user.get_host())
            else:
                logger.info("Not logged in.")
            sys.exit()
        else:
            tank.set_current_user(ShotgunAuthenticator(DefaultsManager()).get_user())

        if len(cmd_line) == 0:
            # > tank, no arguments
            # engine mode, using CWD
            exit_code = run_engine_cmd(logger, pipeline_config_root, [os.getcwd()], None, True, [])

        # special case when we are called from shotgun
        elif cmd_line[0] == "shotgun_run_action":
            exit_code = shotgun_run_action(logger,
                                           install_root,
                                           pipeline_config_root,
                                           is_localized,
                                           cmd_line[1:])

        # special case when we are called from shotgun
        elif cmd_line[0] == "shotgun_cache_actions":
            exit_code = shotgun_cache_actions(logger, pipeline_config_root, cmd_line[1:])

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


            exit_code = run_engine_cmd(logger, pipeline_config_root, ctx_list, cmd_name, using_cwd, cmd_args)

    except AuthenticationModuleError, e:
        logger.info("Authentication was cancelled.")
        # Error messages and such have already been handled by the method that threw this exception.
        sys.exit(8)

    except TankError, e:
        logger.info("")
        if debug_mode:
            # full stack trace
            logger.exception("A TankError was raised: %s" % e)
        else:
            # one line report
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

    # Do not use 8, it is alread being used when login was cancelled.

    logger.debug("Exiting with exit code %s" % exit_code)
    sys.exit(exit_code)
