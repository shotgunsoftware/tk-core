# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import with_statement
import sys
import os
import cgi
import re
import logging
import string
import tank
import textwrap
import datetime
from tank.errors import TankError, TankInitError
from tank.commands.tank_command import get_actions, run_action
from tank.commands.clone_configuration import clone_pipeline_configuration_html
from tank.commands.core_upgrade import TankCoreUpdater
from tank.commands.action_base import Action
from tank.util import shotgun
from tank.util import shotgun_entity
from tank.platform import constants as platform_constants
from tank.authentication import ShotgunAuthenticator
from tank.authentication import AuthenticationError
from tank.authentication import ShotgunAuthenticationError
from tank.authentication import AuthenticationCancelled
from tank.authentication import IncompleteCredentials
from tank.authentication import CoreDefaultsManager
from tank.commands import constants as command_constants
from tank_vendor import yaml
from tank.platform import engine
from tank import pipelineconfig_utils
from tank import LogManager

# the logger used by this file is sgtk.tank_cmd
logger = LogManager.get_logger("tank_cmd")

# custom log formatter for the tank command
formatter = None

###############################################################################################
# Constants

ARG_SCRIPT_NAME = "script-name"
ARG_SCRIPT_KEY = "script-key"
ARG_CREDENTIALS_FILE = "credentials-file"

SHOTGUN_ENTITY_TYPES = ['ActionMenuItem', 'ApiUser', 'AppWelcomeUserConnection', 'Asset', 'AssetAssetConnection',
                        'AssetBlendshapeConnection', 'AssetElementConnection', 'AssetEpisodeConnection',
                        'AssetLevelConnection', 'AssetLibrary', 'AssetMocapTakeConnection', 'AssetSceneConnection',
                        'AssetSequenceConnection', 'AssetShootDayConnection', 'AssetShotConnection', 'Attachment',
                        'BannerUserConnection', 'Blendshape', 'Booking', 'Camera', 'CameraMocapTakeConnection',
                        'Candidate', 'ClientUser', 'Cut', 'CutItem', 'CutVersionConnection', 'Delivery',
                        'DeliveryTarget', 'Delivery_sg_assets_Connection', 'Delivery_sg_shots_Connection',
                        'Delivery_sg_versions_Connection', 'Department', 'Element', 'ElementShotConnection', 'Episode',
                        'EventLogEntry', 'FilesystemLocation', 'Group', 'GroupUserConnection', 'HumanUser', 'Icon',
                        'Launch', 'LaunchSceneConnection', 'LaunchShotConnection', 'Level', 'LocalStorage', 'MocapPass',
                        'MocapSetup', 'MocapTake', 'MocapTakeRange', 'MocapTakeRangeShotConnection', 'Note', 'Page',
                        'PageHit', 'PageSetting', 'Performer', 'PerformerMocapTakeConnection',
                        'PerformerRoutineConnection', 'PerformerShootDayConnection', 'PermissionRuleSet', 'Phase',
                        'PhysicalAsset', 'PhysicalAssetMocapTakeConnection', 'PipelineConfiguration', 'Playlist',
                        'PlaylistShare', 'PlaylistVersionConnection', 'Project', 'ProjectUserConnection',
                        'PublishEvent', 'PublishedFile', 'PublishedFileDependency', 'PublishedFileType', 'Reel',
                        'Release', 'ReleaseTicketConnection', 'Reply', 'Revision', 'RevisionRevisionConnection',
                        'RevisionTicketConnection', 'Routine', 'RvLicense', 'Scene', 'Sequence', 'ShootDay',
                        'ShootDaySceneConnection', 'Shot', 'ShotShotConnection', 'Shot_sg_animations_Connection',
                        'Shot_sg_deliverables_Connection', 'Slate', 'SourceClip', 'Status', 'Step', 'TankAction',
                        'TankContainer', 'TankDependency', 'TankPublishedFile', 'TankType', 'Task', 'TaskDependency',
                        'TaskTemplate', 'TemerityNode', 'Ticket', 'TicketTicketConnection',
                        'Ticket_sg_related_assets_Connection', 'TimeLog', 'Tool', 'Version', 'WatermarkingPreset']

SHOTGUN_ENTITY_TYPES.extend(["CustomEntity%02d"%x for x in range(1, 51)])
SHOTGUN_ENTITY_TYPES.extend(["CustomNonProjectEntity%02d"%x for x in range(1, 31)])
SHOTGUN_ENTITY_TYPES.extend(["CustomThreadedEntity%02d"%x for x in range(1, 16)])

###############################################################################################
# Helpers and General Stuff

class AltCustomFormatter(logging.Formatter):
    """
    Custom logging formatter for the tank command.

    This logger handles html-style outputting, intended for
    messages that are sent back to the Shotgun UI (via the sg engine).

    Non-html output is formatted to be cut at 80 chars
    in order to make it easily readable.
    """
    def __init__(self, *args, **kwargs):
        """
        Constructor
        """
        self._html = False
        self._num_errors = 0
        logging.Formatter.__init__(self, *args, **kwargs)

    def enable_html_mode(self):
        """
        Turns on html output
        """
        self._html = True

    def get_num_errors(self):
        """
        Returns the number of items that have been logged so far.
        """
        return self._num_errors

    def format(self, record):

        if record.levelno > logging.WARNING:
            self._num_errors += 1

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

            if not("Code Traceback" in record.msg or record.levelno < logging.INFO):
                # do not wrap exceptions and debug
                # wrap other log levels on an 80 char wide boundary
                lines = []

                if sys.version_info < (2,6):
                    # python 2.5 doesn't support all params
                    wrapped_lines = textwrap.wrap(record.msg, width=78, break_long_words=False)
                else:
                    wrapped_lines = textwrap.wrap(record.msg, width=78, break_long_words=False, break_on_hyphens=False)

                for x in wrapped_lines:
                    lines.append(x)
                record.msg = "\n".join(lines)

        return logging.Formatter.format(self, record)


def show_help():
    """
    Prints main help text to logger.
    """

    info = """
Welcome to the Shotgun pipeline toolkit!

This command lets you control Toolkit from a shell. You can start apps and
engines via the Tank command. You can also run various admin commands.


General options and info
----------------------------------------------
- To show this help, add a -h or --help flag.
- To display verbose debug, add a --debug flag.
- To provide a script name and script key on the command line for
  authentication, add the --script-name=scriptname and
  --script-key=scriptkey arguments anywhere on the command line.
- To provide a script user and script key in a file for authentication,
  add the --credentials-file=/path/to/credential/file anywhere on the
  command line. The credentials file should be in the YAML format with keys
  script-name and script-key set. For example:
  script-name: Toolkit
  script-key: cb412dbf815bf9d4c257f648d9ec99


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

Log out of the current user (no context required):
> tank logout

"""
    for x in info.split("\n"):
        logger.info(x)


def ensure_authenticated(script_name, script_key):
    """
    Make sure that there is a current toolkit user set.
    May prompt for a login/password if needed. Note that if command line
    arguments are used, the current user will be overriden only for this
    invocation of the tank command and future invocations without credentials
    on the command line will use the current default user. If no command line
    credentials are provided and no script user is set, then the user will be
    prompted for his credentials and those will be remembered in future
    invocations until that user logs out.

    :param script_name: Name of the script to authenticate with. Can be None.
    :param script_key: Key of the script to authenticate with. Can be None.
    """
    # create a core-level defaults manager.
    # this will read site details from shotgun.yml
    core_dm = CoreDefaultsManager()
    # set up the authenticator
    shotgun_auth = ShotgunAuthenticator(core_dm)

    if script_name and script_key:
        user = shotgun_auth.create_script_user(
            api_script=script_name,
            api_key=script_key
        )
    else:
        # request a user, either by prompting the user or by pulling out of
        # saved sessions etc.
        user = shotgun_auth.get_user()
    # set the current toolkit user
    tank.set_authenticated_user(user)



###############################################################################################
# Shotgun Actions Management

def _run_shotgun_command(tk, action_name, entity_type, entity_ids):
    """
    Helper method. Starts the shotgun engine and
    executes a command.

    :param tk:              toolkit API instance
    :param action_name:     name of action to execute
    :param entity_type:     shotgun entity type to execute the command on
    :param entity_ids:      entity ids to execute the command on
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

    logger.debug("Launched engine %s" % e)
    logger.debug("Registered commands: %s" % e.commands.keys())

    cmd = e.commands.get(action_name)
    if cmd:
        callback = cmd["callback"]

        # check if we are running a pre-013 engine
        # (this can be removed at a later point)
        if hasattr(e, "execute_old_style_command"):
            # 013 compliant engine!
            #
            # choose between std style callbacks or special
            # shotgun (legacy) multi select callbacks
            # this is detected by register_command and a special
            # flag is set for the multi select ones
            if platform_constants.LEGACY_MULTI_SELECT_ACTION_FLAG in cmd["properties"]:
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
    The cache is per type and per operating system.

    :param tk:              toolkit API instance
    :param entity_type:     type of the entity that we want to write the cache
                            for
    :param cache_file_name: name of the file used to store the cached data
    """
    cache_path = os.path.join(tk.pipeline_configuration.get_shotgun_menu_cache_location(), cache_file_name)

    # start the shotgun engine, load the apps
    e = engine.start_shotgun_engine(tk, entity_type, tk.context_empty())

    # get list of actions
    engine_commands = e.commands

    # insert special system commands
    if entity_type.lower() == "project":
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

        title = cmd_params["properties"].get("title", cmd_name)
        supports_multiple_sel = cmd_params["properties"].get(
            "supports_multiple_selection", False)
        deny = ",".join(cmd_params["properties"].get("deny_permissions", []))
        icon = cmd_params["properties"].get("icon", "")
        description = cmd_params["properties"].get("description", "")

        entry = [ cmd_name, title, deny, str(supports_multiple_sel),
                  icon, description ]

        # sanitize the fields to make sure that they do not break the cache
        # format
        sanitized = [ token.replace("\n", " ").replace("$", "_")
                      for token in entry ]

        res.append("$".join(sanitized))

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


def shotgun_cache_actions(pipeline_config_root, args):
    """
    Executes the special shotgun cache actions command
    """
    logger.debug("Running shotgun_cache_actions command")
    logger.debug("Arguments passed: %s" % args)

    try:
        tk = tank.tank_from_path(pipeline_config_root)
        # attach our logger to the tank instance
        # this will be detected by the shotgun and shell engines
        # and used.
        tk.log = logger
    except TankError, e:
        raise TankError("Could not instantiate an Sgtk API Object! Details: %s" % e )

    # params: entity_type, cache_file_name
    if len(args) != 2:
        raise TankError("Invalid arguments! Pass entity_type, cache_file_name")

    entity_type = args[0]
    cache_file_name = args[1]

    num_log_messages_before = formatter.get_num_errors()
    try:
        _write_shotgun_cache(tk, entity_type, cache_file_name)
    except TankError, e:
        logger.error("Error writing shotgun cache file: %s" % e)
    except Exception, e:
        logger.exception("A general error occurred.")
    num_log_messages_after = formatter.get_num_errors()

    # check if there were any log output. This is an indication that something
    # weird and unexpected has happened...
    if (num_log_messages_after - num_log_messages_before) > 0:
        logger.info("")
        logger.warning("Generating the cache file for this environment may have resulted in some "
                    "actions being omitted because of configuration errors. You may need to "
                    "clear the cache by running the following command:")

        code_css_block = "display: block; padding: 0.5em 1em; border: 1px solid #bebab0; background: #faf8f0;"

        logger.info("")
        if sys.platform == "win32":
            tank_cmd = os.path.join(pipeline_config_root, "tank.bat")
        else:
            tank_cmd = os.path.join(pipeline_config_root, "tank")
        logger.info("<code style='%s'>%s clear_shotgun_menu_cache</code>" % (code_css_block, tank_cmd))
        logger.info("")
        
        # return with an error code to indicate a failure to the caller
        return 1
    
    # return success error code
    return 0

def shotgun_run_action_auth(install_root, pipeline_config_root, is_localized, args):
    """
    Executes the special shotgun run action command from inside of shotgun.
    Authenticated version.

    This method expects the following arguments to be passed via the args param:
    args[0]: name of the action
    args[1]: entity type to operate on
    args[2]: list of entity ids as a string, e.g. '1,2,3'
    args[3]: shotgun user login requesting this command
    args[4]: rot-13 shifted password for the user. Can be set to "-" - in that case,
             this is a hint to toolkit to try to authenticate via a
             cached session token
    args[5:]: reserved for future use. This method will *not* error
              if unexpected args are passed to it.

    :param install_root: Root of the toolkit core installation
    :param pipeline_config_root: Root of the pipeline configuration
    :param is_localized: True if the pipeline configuration has been localized
    :param args: list of arguments passed from Shotgun.
    """
    logger.debug("Running shotgun_run_action_auth command")

    action_name = args[0]
    entity_type = args[1]
    entity_ids_str = args[2].split(",")
    entity_ids = [int(x) for x in entity_ids_str]
    login = args[3]
    rot13_password = args[4]

    # un-swizzle the password
    rot13 = string.maketrans("NOPQRSTUVWXYZnopqrstuvwxyzABCDEFGHIJKLMabcdefghijklm",
                             "ABCDEFGHIJKLMabcdefghijklmNOPQRSTUVWXYZnopqrstuvwxyz")
    password = string.translate(rot13_password, rot13)

    # now, first try to authenticate
    core_dm = CoreDefaultsManager()
    sa = ShotgunAuthenticator(core_dm)

    # If there is a default user and it has no name, we should authenticate
    # with it since it's the script user and we have to remain backwards
    # compatible.
    default_user = sa.get_default_user()
    if default_user and not default_user.login:
        # there is a default script user - this takes precedence.
        tank.set_authenticated_user(default_user)
    else:
        # no default user. Have to authenticate
        if password == "-":
            # no password given from shotgun. Try to use a stored session token
            try:
                user = sa.create_session_user(login)
                if user.are_credentials_expired():
                    raise IncompleteCredentials("Session token is expired.")
            except IncompleteCredentials:
                # report back to the Shotgun javascript integration
                # this error message will trigger the javascript to
                # prompt the user for a password and run this method
                # again, this time with an actual password rather
                # than an empty string.
                logger.error("Cannot authenticate user '%s'" % login)
                return

        else:
            # we have a password, so create a session user
            # based on full credentials.
            # the shotgun authenticator will store a session
            # token for this user behind the scenes, so next time,
            # we can create a user based on the login only.
            try:
                user = sa.create_session_user(login, password=password)
            except AuthenticationError:
                # this message will be sent back to the user via the
                # javascript integration
                logger.error("Invalid password! Please try again.")
                return

        # tell tk about our current user!
        tank.set_authenticated_user(user)

    # and fire off the action
    return _shotgun_run_action(install_root,
                               pipeline_config_root,
                               is_localized,
                               action_name,
                               entity_type,
                               entity_ids)

def shotgun_run_action(install_root, pipeline_config_root, is_localized, args):
    """
    Executes the special shotgun run action command from inside of shotgun.
    Legacy - unauthenticated version.

    All modern versions of Shotgun will be running the shotgun_run_action_auth method.
    this method is to serve users who are running an updated version of core with
    an older version of Shotgun

    This method expects the following arguments to be passed via the args param:
    args[0]: name of the action
    args[1]: entity type to operate on
    args[2]: list of entity ids as a string, e.g. '1,2,3'
    args[3]: shotgun user login requesting this command

    :param install_root: Root of the toolkit core installation
    :param pipeline_config_root: Root of the pipeline configuration
    :param is_localized: True if the pipeline configuration has been localized
    :param args: list of arguments passed from Shotgun.
    """
    logger.debug("Running shotgun_run_action command")
    logger.debug("Arguments passed: %s" % args)

    # params: action_name, entity_type, entity_ids
    if len(args) != 3:
        raise TankError("Invalid arguments! Pass action_name, entity_type, comma_separated_entity_ids")

    # all modern versions of Shotgun will be running the shotgun_run_action_auth method.
    # this method is to serve users who are running an updated version of core with
    # an older version of Shotgun

    # in this case, we cannot prompt for a login/password
    # so we have rely on the built-in user that is given by the defaults manager
    # in our case, the tk-core defaults manager returns the credentials stored in
    # the shotgun.yml config file.
    core_dm = CoreDefaultsManager()
    sa = ShotgunAuthenticator(core_dm)
    user = sa.get_default_user()
    tank.set_authenticated_user(user)

    action_name = args[0]
    entity_type = args[1]
    entity_ids_str = args[2].split(",")
    entity_ids = [int(x) for x in entity_ids_str]

    return _shotgun_run_action(install_root,
                               pipeline_config_root,
                               is_localized,
                               action_name,
                               entity_type,
                               entity_ids)

def _shotgun_run_action(install_root, pipeline_config_root, is_localized, action_name, entity_type, entity_ids):
    """
    Executes a Shotgun action.

    :param install_root: Root of the toolkit core installation
    :param pipeline_config_root: Root of the pipeline configuration
    :param is_localized: True if the pipeline configuration has been localized
    :param ation_name: Name of action to execute (e.g launch_maya)
    :param entity_type: Entity type to execute action for
    :param entity_ids: list of entity ids (as ints) to pass to the action.
    """
    try:
        tk = tank.tank_from_path(pipeline_config_root)
        # attach our logger to the tank instance
        # this will be detected by the shotgun and shell engines
        # and used.
        tk.log = logger
    except TankError, e:
        raise TankError("Could not instantiate an Sgtk API Object! Details: %s" % e )

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
        clone_pipeline_configuration_html(logger,
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
        installer = TankCoreUpdater(install_root, logger)

        cv = installer.get_current_version_number()
        lv = installer.get_update_version_number()
        logger.info("You are currently running version %s of the Shotgun Pipeline Toolkit." % cv)

        if not is_localized:
            logger.info("")
            logger.info("Your core API is located in <code>%s</code> and is shared with other "
                     "projects." % install_root)

        logger.info("")

        status = installer.get_update_status()

        if status == TankCoreUpdater.UP_TO_DATE:
            logger.info("<b>You are up to date! There is no need to update the Toolkit Core API at this time!</b>")

        elif status == TankCoreUpdater.UPDATE_BLOCKED_BY_SG:
            req_sg = installer.get_required_sg_version_for_update()
            logger.warning("<b>A new version (%s) of the core API is available however "
                        "it requires a more recent version (%s) of Shotgun!</b>" % (lv, req_sg))

        elif status == TankCoreUpdater.UPDATE_POSSIBLE:

            (summary, url) = installer.get_release_notes()

            logger.info("<b>A new version of the Toolkit API (%s) is available!</b>" % lv)
            logger.info("")
            logger.info("<b>Change Summary:</b> %s <a href='%s' target=_new>"
                     "Click for detailed Release Notes</a>" % (summary, url))
            logger.info("")
            logger.info("In order to upgrade, execute the following command in a shell:")
            logger.info("")

            if sys.platform == "win32":
                tank_cmd = os.path.join(install_root, "tank.bat")
            else:
                tank_cmd = os.path.join(install_root, "tank")

            logger.info("<code style='%s'>%s core</code>" % (code_css_block, tank_cmd))

            logger.info("")

        else:
            raise TankError("Unknown Upgrade state!")


    elif action_name == "__upgrade_check":

        # special built in command that simply tells the user to run the tank command

        code_css_block = "display: block; padding: 0.5em 1em; border: 1px solid #bebab0; background: #faf8f0;"

        logger.info("In order to check if your installed apps and engines are up to date, "
                 "you can run the following command in a console:")

        logger.info("")

        if sys.platform == "win32":
            tank_cmd = os.path.join(pipeline_config_root, "tank.bat")
        else:
            tank_cmd = os.path.join(pipeline_config_root, "tank")

        logger.info("<code style='%s'>%s updates</code>" % (code_css_block, tank_cmd))

        logger.info("")

    else:
        _run_shotgun_command(tk, action_name, entity_type, entity_ids)


###############################################################################################
# Shell Actions Management

def _resolve_shotgun_pattern(entity_type, name_pattern):
    """
    Resolve a pattern given an entity. Search the 'name' field
    for an entity. For most types, this is the code field.
    Raise exceptions unless there is a single matching item.

    :param entity_type: Entity type to search
    :param name_pattern: Name pattern to search for
    :returns: (entity id, name)
    """

    name_field = shotgun_entity.get_sg_entity_name_field(entity_type)

    sg = shotgun.get_sg_connection()

    logger.debug("Shotgun: find(%s, %s contains %s)" % (entity_type, name_field, name_pattern) )
    data = sg.find(entity_type, [[name_field, "contains", name_pattern]], [name_field])
    logger.debug("Got data: %r" % data)

    if len(data) == 0:
        raise TankError("No Shotgun %s matching the pattern '%s'!" % (entity_type, name_pattern))

    elif len(data) > 1:
        names = ["'%s'" % x[name_field] for x in data]
        raise TankError("More than one %s matching pattern '%s'. Matching items are %s. "
                        "Please be more specific." % (entity_type, name_pattern, ", ".join(names)))

    # got a single item
    return (data[0]["id"], data[0][name_field])



def _list_commands(tk, ctx):
    """
    Outputs a list of commands to the logger given the current context.
    """
    # get all the action objets (commands) suitable for the current context
    (aa, engine) = get_actions(logger, tk, ctx)

    logger.info("")
    logger.info("The following commands are available:")

    # group by category
    by_category = {}
    for x in aa:
        if x.category not in by_category:
            by_category[x.category] = []
        by_category[x.category].append(x)

    # Add Login category manually, since they are not commands per-se since they are run before the
    # engine is initialized.

    by_category.setdefault("Login", []).append(
        Action("logout", "unused", "Log out of the current user (no need for a context).", "Login")
    )

    num_engine_commands = 0
    for cat in sorted(by_category.keys()):
        logger.info("")
        logger.info("=" * 50)
        logger.info("%s Commands" % cat)
        logger.info("=" * 50)
        logger.info("")
        for cmd in sorted(by_category[cat], key=lambda c: c.name):
            logger.info(cmd.name)
            logger.info("-" * len(cmd.name))
            logger.info(cmd.description)
            logger.info("")
            # keep track of number of engine commands
            if cmd.mode == Action.ENGINE:
                num_engine_commands += 1



    if num_engine_commands == 0:
        # not a fully populated setup - so display some interactive help!
        logger.info("")
        logger.info("=" * 50)
        logger.info("Didn't find what you were looking for?")
        logger.info("=" * 50)
        logger.info("")

        if tk is None:
            # we have nothing.
            logger.info("You have launched the Tank command without a Project. This means that you "
                     "are only getting a small number of global system commands in the list of "
                     "commands. Try pointing the tank command to a project location, for example: ")
            logger.info("")
            logger.info("> tank Project XYZ")
            logger.info("> tank Shot ABC123")
            logger.info("> tank Asset ALL")
            logger.info("> tank /mnt/projects/my_project/shots/ABC123")
            logger.info("")

        elif ctx is None:
            # we have a project but no context.
            logger.info("You have launched the Tank command but not pointed it at a specific "
                     "work area. You are running tank from the configuration found in "
                     "'%s' but no specific asset or shot was selected so only a generic list "
                     "of commands will be displayed. Try pointing the tank command to a more "
                     "specific location, for example: " % tk.pipeline_configuration.get_path())
            logger.info("")
            logger.info("> tank Shot ABC123")
            logger.info("> tank Asset ALL")
            logger.info("> tank /mnt/projects/my_project/shots/ABC123")
            logger.info("")

        else:
            # we have a context but no engine!
            # no engine may be because of a couple of reasons:
            # 1. no environment was found for the context
            # 2. no shell engine was installed
            # 3. no apps are installed for the shell engine

            env = tank.platform.engine.get_environment_from_context(tk, ctx)
            if env is None:
                # no environment for context
                logger.info("Your current context ('%s') does not have a matching Sgtk Environment. "
                         "An environment is a part of the configuration and is used to define what "
                         "tools are available in a certain part of the pipeline. For example, you "
                         "may have a Shot and and Asset environment, defining the different tools "
                         "needed for asset work and shot work. Try navigating to a more specific "
                         "part of your project setup, or contact support if you have further "
                         "questions." % ctx)


            elif command_constants.SHELL_ENGINE not in env.get_engines():
                # no shell engine installed
                logger.info("Looks like the environment configuration '%s', which is associated "
                         "with the current context (%s), does not have a shell engine "
                         "installed. The shell engine is necessary if you want to run apps using "
                         "the tank command. You can install it by running the install_engine "
                         "command." % (env.disk_location, ctx))

            else:
                # number engine commands is zero
                logger.info("Looks like you don't have any apps installed that can run in the shell "
                         "engine! Try installing apps using the install_app command or start a new "
                         "project based on the latest Sgtk default starter configuration if you want "
                         "to get a working example of how the shell engine can be configured.")


    logger.info("")
    logger.info("")


def _resolve_shotgun_entity(entity_type, entity_search_token, constrain_by_project_id):
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
    name_field = shotgun_entity.get_sg_entity_name_field(entity_type)

    try:
        # build up filters
        shotgun_filters = []

        if entity_search_token != "ALL":
            shotgun_filters.append([name_field, "contains", entity_search_token])

        if constrain_by_project_id:
            # append project constraint
            shotgun_filters.append(["project", "is" , {"type": "Project", "id": constrain_by_project_id}])

        logger.debug("Shotgun: find(%s, %s)" % (entity_type, shotgun_filters))
        entities = sg.find(entity_type,
                           shotgun_filters,
                           [name_field, "description", "entity", "link", "project"])
        logger.debug("Got data: %r" % entities)
    except Exception, e:
        raise TankError("An error occurred when searching in Shotgun: %s" % e)

    selected_entity = None

    if len(entities) == 0:
        logger.info("")
        logger.info("Could not find a %s with a name containing '%s' in Shotgun!" % (entity_type, entity_search_token))
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


        logger.info("")
        logger.info("More than one item matching your input:" )
        logger.info("")
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

            logger.info("".join(chunks))


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

            logger.info(chopped_desc)

            logger.info("")


        if entity_search_token != "ALL":
            # don't display this helpful hint if they have used the special ALL keyword
            logger.info("More than one item matched your search phrase '%s'! "
                     "Please enter a more specific search phrase in order to narrow it down "
                     "to a single match. If there are several items with the same name, "
                     "you can use the @id field displayed to specify a particular "
                     "object (e.g. '%s @123')." % (entity_search_token, entity_type))

        if constrain_by_project_id is None:
            # not using any project filters
            logger.info("")
            logger.info("If you want to search on items from a particular project, you can either "
                     "run the tank command from that particular project or prefix your search "
                     "string with a project name. For example, if you want to only see matches "
                     "from a project named VFX, search for '%s VFX:%s'" % (entity_type, entity_search_token))

        logger.info("")
        raise TankError("Please try again with a more specific search!")



    # make sure there is a project associated with this entity!
    # selected_entity now has an entity populated in it.
    if entity_type != "Project":
        if selected_entity.get("project") is None:
            raise TankError("Found %s %s however this item is not associated with "
                            "a Project!" % (entity_type, selected_entity[name_field]))

        logger.info("- Found %s %s (Project '%s')" % (entity_type,
                                                 selected_entity[name_field],
                                                 selected_entity["project"]["name"]))

    else:
        # project case
        logger.info("- Found %s %s" % (entity_type, selected_entity[name_field]))


    return selected_entity["id"]


def run_engine_cmd(pipeline_config_root, context_items, command, using_cwd, args):
    """
    Launches an engine and potentially executes a command.

    :param pipeline_config_root: pipeline config location
    :param context_items: list of strings to describe context. Either ["path"],
                               ["entity_type", "entity_id"] or ["entity_type", "entity_name"]

    :param engine_name: engine to run
    :param command: command to run - None will display a list of commands
    :param using_cwd: Was the context passed based on the current work folder?
    """
    logger.debug("")
    logger.debug("Context items: %s" % str(context_items))
    logger.debug("Command: %s" % command)
    logger.debug("Command Arguments: %s" % args)
    logger.debug("Sgtk Pipeline Config Location: %s" % pipeline_config_root)
    logger.debug("Location of this script (__file__): %s" % os.path.abspath(__file__))

    logger.info("")

    logger.info("Welcome to the Shotgun Pipeline Toolkit!")
    logger.info("For documentation, see https://support.shotgunsoftware.com")

    # Now create a tk instance and a context if possible
    ctx = None
    tk = None

    if len(context_items) == 1:
        # path mode: e.g. tank /foo/bar/baz
        # create a context given a path as the input

        ctx_path = context_items[0]

        if using_cwd:
            logger.info("Starting Toolkit for your current path '%s'" % ctx_path)
        else:
            logger.info("Starting toolkit for path '%s'" % ctx_path)

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
                logger.debug("Instantiating Sgtk raised: %s" % e)

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
                logger.info("- The path is not associated with any Shotgun object.")
                logger.info("- Falling back on default project settings.")

                if tk.pipeline_configuration.is_site_configuration():
                    # Site config doesn't have a project, so the context is empty.
                    ctx = tk.context_empty()
                else:
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
            logger.info(
                "- You are running a project specific tank command. Only items that are part "
                "of this project will be considered."
            )

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
                (project_id, project_name) = _resolve_shotgun_pattern("Project", proj_token)
                logger.info("- Searching in project '%s' only" % project_name)


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
            name_field = shotgun_entity.get_sg_entity_name_field(entity_type)

            # first try by name - e.g. a shot named "123"
            filters = [[name_field, "is", entity_search_token]]
            if project_id:
                # when running a per project tank command, make sure we
                # filter out all other items in other projects.
                filters.append( ["project", "is", {"type": "Project", "id": project_id} ])

            logger.debug("Shotgun: find(%s, %s)" % (entity_type, filters))
            data = sg.find(entity_type, filters, ["id", name_field])
            logger.debug("Got data: %r" % data)

            if len(data) == 0:
                # no exact match. Assume the string is an id
                logger.info("- Did not find a %s named '%s', will look for a %s with id %s "
                         "instead." % (entity_type, entity_search_token, entity_type, entity_search_token))
                entity_id = int(entity_search_token)

                # now we have our entity id, make sure we don't search for this as an expression
                run_expression_search = False

        elif entity_search_token.startswith("@") and entity_search_token[1:].isdigit():
            # special syntax to ensure that you can unambiguously refer to ids
            # 'tank Shot @123' means that you specifically refer to a Shot with id 123,
            # not a shot named "123". This syntax is explicit and is also faster to evaluate
            entity_id = int(entity_search_token[1:])
            logger.info("- Looking for a %s with id %d." % (entity_type, entity_id))
            logger.debug("Direct @id syntax - will resolve entity id %d" % entity_id)
            # now we have our entity id, make sure we don't search for this as an expression
            run_expression_search = False

        if run_expression_search:
            # use normal string based parse methods
            # we are now left with the following cases to resolve
            # tank Entitytype name_expression
            entity_id = _resolve_shotgun_entity(entity_type, entity_search_token, project_id)

        # now initialize toolkit and set up the context.
        try:
            tk = tank.tank_from_entity(entity_type, entity_id)
        except TankInitError as exc:
            # If we failed to get an object back, a likely cause is that the entity
            # has been retired. In the situation where an unregister_folders command
            # is being called, we can give the user some better feedback concerning
            # how to unregister the folder using the path instead of the entity.
            if command == "unregister_folders":
                raise TankInitError(
                    "%s If you want to unregister folders associated with this "
                    "entity, you can do so by calling the unregister_folders "
                    "command on the associated path instead: "
                    "\"tank unregister_folders /path/to/folder\"" % exc.message
                )
            raise

        ctx = tk.context_from_entity(entity_type, entity_id)


    logger.debug("Sgtk API and Context resolve complete.")
    logger.debug("Sgtk API: %s" % tk)
    logger.debug("Context: %s" % ctx)

    logger.info("- Running as user '%s'" % tank.get_authenticated_user() )

    if tk is not None:
        logger.info("- Using configuration '%s' and Core %s" % (tk.pipeline_configuration.get_name(), tk.version))
        # attach our logger to the tank instance
        # this will be detected by the shotgun and shell engines and used.
        tk.log = logger

    if ctx is not None:
        logger.info("- Setting the Context to %s." % ctx)

    if command is None:
        return _list_commands(tk, ctx)
    else:
        # pass over to the tank commands api - this will take over command execution,
        # setup the objects accordingly etc.
        return run_action(logger, tk, ctx, command, args)


def _extract_args(cmd_line, args):
    """
    Extract specified arguments and sorts them. Also removes them from the
    command line.

    :param cmd_line: Array of command line arguments.
    :param args: List of arguments to extract.

    :returns: A tuple. The first element is a list of key, value tuples representing each arguments.
        The second element is the cmd_line list without the arguments that were
        extracted.
    """
    # Find all instances of each argument in the command line
    found_args = []
    for cmd_line_token in cmd_line:
        for arg in args:
            if cmd_line_token.startswith("--%s=" % arg):
                found_args.append(cmd_line_token)

    # Strip all these arguments from the command line.
    new_cmd_line = [
        argument for argument in cmd_line if argument not in found_args
    ]

    arguments = []

    # Create a list of tuples for each argument we found.
    for arg in found_args:
        pos = arg.find("=")
        # Take everything after the -- up to but not including the =
        arg_name = arg[2:pos]
        arg_value = arg[pos + 1:]
        arguments.append((arg_name, arg_value))

    return arguments, new_cmd_line


def _validate_only_once(args, arg):
    """
    Validates that an argument is only present once.

    :param args: List of tuples of arguments that were extracted from the command line.
    :param arg: Argument to validate

    :raises IncompleteCredentials: If an argument has been specified more than once,
                                this exception is raised.
    """
    occurences = filter(lambda a: a[0] == arg, args)
    if len(occurences) > 1:
        raise IncompleteCredentials("argument '%s' specified more than once." % arg)


def _validate_args_cardinality(args, arg1, arg2):
    """
    Makes sure that there are no more and no less than 1 value for each argument.

    :param args: List of argument tuples.
    :param arg1: First argument to test for.
    :param arg2: Second argument to test for.

    :raises IncompleteCredentials: When there is more or less than 1 value for
                                a given argument, this exception is raised.
    """
    # Too few parameters, find out which one is missing, let the user know
    # which is missing.
    if len(args) < 2:
        raise IncompleteCredentials("missing argument '%s'" % (arg1 if args[0][0] == arg2 else arg2))

    # Make sure each arguments are not specified more than once.
    _validate_only_once(args, arg1)
    _validate_only_once(args, arg2)


def _read_credentials_from_file(auth_path):
    """
    Reads the credentials from a file and returns a list of tuples for each
    script-key and script-name arguments. Any other values are ignored.

    Here's a sample file:

    script-name: Toolkit
    script-key: cb412dbf815bf9d4c257f648d9ec996722b4b452fc4c54dfbd0684d56fa65956


    :param auth_path: Path to a file with credentials.

    :returns: A list of key, value pairs for values parsed. For example,
        [("script-name", "name"), ("script-key", "12345")]

    :raises IncompleteCredentials: If the file doesn't exist, this exception is raised.
    """
    if not os.path.exists(auth_path):
        raise IncompleteCredentials("credentials file does not exist.")
    # Read the dictionary from file
    with open(auth_path) as auth_file:
        file_data = yaml.load(auth_file)

    args = [
        (k, v) for k, v in file_data.iteritems() if k in [ARG_SCRIPT_NAME, ARG_SCRIPT_KEY]
    ]

    return args


def _extract_credentials(cmd_line):
    """
    Finds credentials from the command-line if the user specified them and
    removes them from the array.

    :param cmd_line: Array of arguments passed to the tank command.

    :returns: A tuple of (filtered command line arguments, credentials).
    """

    # Extract the credential pairs.
    script_user_credentials, cmd_line = _extract_args(cmd_line, [ARG_SCRIPT_NAME, ARG_SCRIPT_KEY])
    file_credentials_path, cmd_line = _extract_args(cmd_line, [ARG_CREDENTIALS_FILE])

    # make sure we're not mixing both set of arguments
    if file_credentials_path and script_user_credentials:
            raise IncompleteCredentials("can't mix command line credentials and file credentials.")

    # If we have credentials in a file
    if file_credentials_path:
        # Validate it's only been specified once.
        _validate_only_once(file_credentials_path, ARG_CREDENTIALS_FILE)
        # Read the credentials from file
        script_user_credentials = _read_credentials_from_file(
            file_credentials_path[0][1]
        )

    if script_user_credentials:
        _validate_args_cardinality(script_user_credentials, ARG_SCRIPT_NAME, ARG_SCRIPT_KEY)
        return cmd_line, dict(script_user_credentials)

    # If no elements were specified, that's ok.
    return cmd_line, {}


if __name__ == "__main__":

    # set up std toolkit logging to file
    LogManager().initialize_base_file_handler(command_constants.SHELL_ENGINE)

    # set up output of all sgtk log messages to stdout
    log_handler = LogManager().initialize_custom_handler(
        logging.StreamHandler(sys.stdout)
    )

    # set up the custom html formatter
    formatter = AltCustomFormatter()
    log_handler.setFormatter(formatter)

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
        LogManager().global_debug = True
        logger.debug("")
        logger.debug("A log file can be found in %s" % LogManager().log_folder)
        logger.debug("")
    cmd_line = [arg for arg in cmd_line if arg != "--debug"]

    # help requested?
    for x in cmd_line:
        if x == "--help" or x == "-h":
            exit_code = show_help()
            sys.exit(exit_code)

    # determine if we are running a localized core API.
    is_localized = pipelineconfig_utils.is_localized(install_root)

    # also we are passing the pipeline config
    # at the back of the args as --pc=foo
    if len(cmd_line) > 0 and cmd_line[-1].startswith("--pc="):
        pipeline_config_root = cmd_line[-1][5:]
    else:
        # no pipeline config parameter passed. But it could be that we are using a localized core
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

        cmd_line, credentials = _extract_credentials(cmd_line)

        if len(cmd_line) > 0 and cmd_line[0].startswith("shotgun_"):
            # we are talking to shotgun, enable html log formatting
            formatter.enable_html_mode()

        if len(cmd_line) == 0:
            # > tank, no arguments
            # engine mode, using CWD

            # first make sure there is a current user
            ensure_authenticated(
                credentials.get("script-name"),
                credentials.get("script-key")
            )

            # now run the command
            exit_code = run_engine_cmd(pipeline_config_root, [os.getcwd()], None, True, [])

        elif cmd_line[0] == "logout":
            core_dm = CoreDefaultsManager()
            sa = ShotgunAuthenticator(core_dm)
            # Clear the saved user.
            user = sa.clear_default_user()
            if user:
                logger.info("Succesfully logged out from %s." % user.host)
            else:
                logger.info("Not logged in.")

        # special case when we are called from shotgun
        elif cmd_line[0] == "shotgun_run_action":
            # note - this pathway is not authenticated from shotgun
            # this is there for backwards compatibility
            exit_code = shotgun_run_action(install_root,
                                           pipeline_config_root,
                                           is_localized,
                                           cmd_line[1:])

        # special case when we are called from shotgun
        elif cmd_line[0] == "shotgun_run_action_auth":
            # note: this pathway retrieves authentication via shotgun
            exit_code = shotgun_run_action_auth(install_root,
                                                pipeline_config_root,
                                                is_localized,
                                                cmd_line[1:])

        # special case when we are called from shotgun
        elif cmd_line[0] == "shotgun_cache_actions":
            # note: this pathway does not require authentication
            exit_code = shotgun_cache_actions(pipeline_config_root, cmd_line[1:])

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

            # first make sure there is a current user
            ensure_authenticated(
                credentials.get("script-name"),
                credentials.get("script-key")
            )

            # now run the command
            exit_code = run_engine_cmd(pipeline_config_root, ctx_list, cmd_name, using_cwd, cmd_args)

    except AuthenticationCancelled:
        logger.info("")
        if LogManager().global_debug:
            # full stack trace
            logger.exception("An AuthenticationCancelled error was raised: %s" % "Authentication was cancelled.")
        else:
            # one line report
            logger.error("Authentication was cancelled.")
        logger.info("")
        # Error messages and such have already been handled by the method that threw this exception.
        exit_code = 8

    except IncompleteCredentials, e:
        logger.info("")
        if LogManager().global_debug:
            # full stack trace
            logger.exception("An IncompleteCredentials exception was raised: %s" % e)
        else:
            # one line report
            logger.error(str(e))
        exit_code = 9

    except ShotgunAuthenticationError, e:
        logger.info("")
        if LogManager().global_debug:
            # full stack trace
            logger.exception("A ShotgunAuthenticationError was raised: %s" % str(e))
        else:
            # one line report
            logger.error(str(e))
        logger.info("")
        exit_code = 10

    except TankError, e:
        logger.info("")
        if LogManager().global_debug:
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

