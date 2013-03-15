"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Looks for updates for installed apps in an environment

"""

import os
import sys
import logging
import textwrap

# make sure that the core API is part of the pythonpath
python_path = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "python"))
sys.path.append(python_path)

from tank.errors import TankError
from tank.platform import constants
from tank.platform import environment
from tank.deploy import administrator
from tank.deploy import console_utils

import tank

##########################################################################################
# deploy stuff

def update_item(log, project_root, env, status, engine_name, app_name=None):
    """
    Performs an upgrade of an engine/app.
    """

    new_descriptor = status["latest"]
    old_descriptor = status["current"]

    # note! Some of these methods further down are likely to pull the apps local
    # in order to do deep introspection. In order to provide better error reporting,
    # pull the apps local before we start
    if not new_descriptor.exists_local():
        log.info("Downloading %s..." % new_descriptor)
        new_descriptor.download_local()

    # create required shotgun fields
    new_descriptor.ensure_shotgun_fields_exist()

    # ensure that all required frameworks have been installed
    tank_api = tank.Tank(project_root)
    console_utils.ensure_frameworks_installed(log, tank_api, new_descriptor, env)

    # now get data for all new settings values in the config
    params = console_utils.get_configuration(log, tank_api, new_descriptor, old_descriptor)

    # awesome. got all the values we need.
    log.info("")
    log.info("")

    # next step is to add the new configuration values to the environment
    if app_name is None:

        data = env.get_engine_settings(engine_name)
        # update with the new settings
        data.update(params)
        env.update_engine_settings(engine_name, data)
        env.update_engine_location(engine_name, new_descriptor.get_location())

    else:

        data = env.get_app_settings(engine_name, app_name)
        # update with the new settings
        data.update(params)
        env.update_app_settings(engine_name, app_name, data)
        env.update_app_location(engine_name, app_name, new_descriptor.get_location())

def process_framework(log, project_root, env, framework_name):
    """
    Ensures that a framework exists on disk.
    """
    log.info("Processing framework %s" % framework_name)
    desc = env.get_framework_descriptor(framework_name)
    
    if not desc.exists_local():
        log.info("Downloading %s..." % desc)
        desc.download_local() 


def process_item(log, project_root, env, engine_name, app_name=None):
    """
    Checks if an app/engine is up to date and potentially upgrades it.

    Returns a dictionary with keys:
    - was_updated (bool)
    - old_descriptor
    - new_descriptor (may be None if was_updated is False)
    """

    if app_name is None:
        log.info("Processing engine %s" % engine_name)
    else:
        log.info("Processing app %s.%s" % (engine_name, app_name))

    status = administrator.check_item_update_status(project_root, env, engine_name, app_name)
    item_was_updated = False

    if status["can_update"]:
        
        # print summary of changes
        console_utils.format_bundle_info(log, status["latest"])
        
        # ask user
        if console_utils.ask_question("Update to the above version?"):
            update_item(log, project_root, env, status, engine_name, app_name)
            item_was_updated = True

    elif status["out_of_date"] == False and not status["current"].exists_local():
        # app is not local! boo!
        if console_utils.ask_question("Current version does not exist locally - download it now?"):
            log.info("Downloading %s..." % status["current"])
            status["current"].download_local()

    elif status["out_of_date"] == False:
        log.info("You are running version %s which is the most recent release." % status["latest"].get_version())

    else:
        # cannot update for some reason
        log.warning(status["update_status"])

    # return data
    d = {}
    d["was_updated"] = item_was_updated
    d["old_descriptor"] = status["current"]
    d["new_descriptor"] = status["latest"]
    return d

##########################################################################################
# main script and startup

def main(log):
    """
    App entry point
    """

    if len(sys.argv) != 2 and len(sys.argv) != 3:
        log.info("")
        log.info("")
        log.info("Check for out of date apps and engines.")
        log.info("")
        log.info("Usage: %s project_root [environment_name]" % sys.argv[0])
        log.info("")
        log.info("")
        log.info("")
        sys.exit(1)

    log.info("Welcome to the Tank update checker!")
    log.info("")

    if len(sys.argv) == 2:
        project_root = sys.argv[1]
        env_name = None
        log.info("This script will check that all apps and engines are up to date")
        log.info("for project %s" % project_root)

        try:
            env_files = constants.get_environments_for_proj(project_root)
            environments = [ environment.Environment(ef) for ef in env_files ]
        except Exception, e:
            raise TankError("Environments could not be loaded! Error reported: %s" % e)

    if len(sys.argv) == 3:
        project_root = sys.argv[1]
        env_name = sys.argv[2]
        log.info("This script will check that all apps and engines are up to date")
        log.info("for project %s, environment %s" % (project_root, env_name))

        try:
            env_file = constants.get_environment_path(env_name, project_root)
            environments = [ environment.Environment(env_file) ]
        except Exception, e:
            raise TankError("Environment %s could not be loaded! Error reported: %s" % (env_name, e))

    log.info("")
    log.info("")

    # check engines and apps
    items = []
    for env in environments:
        log.info("")
        log.info("Processing Environment %s..." % env.name)
        log.info("")
                
        for engine in env.get_engines():
            items.append( process_item(log, project_root, env, engine) )
            log.info("")
            for app in env.get_apps(engine):
                items.append( process_item(log, project_root, env, engine, app) )
                log.info("")
        
        for framework in env.get_frameworks():
            process_framework(log, project_root, env, framework)
        

    # display summary
    log.info("")
    summary = []
    for x in items:
        if x["was_updated"]:

            summary.append("%s was updated from %s to %s" % (x["new_descriptor"],
                                                             x["old_descriptor"].get_version(),
                                                             x["new_descriptor"].get_version()))
            (rel_note_summary, url) = x["new_descriptor"].get_changelog()
            if url:
                summary.append("Change Log: %s" % url)
            summary.append("")

    if len(summary) > 0:
        log.info("Items were updated. Details follow below:")
        log.info("-" * 70)
        for x in summary:
            log.info(x)
        log.info("-" * 70)

    else:
        log.info("All items were already up to date!")

    log.info("")


if __name__ == "__main__":

    log = logging.getLogger("tank.update")
    log.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)s %(message)s")
    ch.setFormatter(formatter)
    log.addHandler(ch)

    exit_code = 1
    try:
        main(log)
        exit_code = 0
    except TankError, e:
        # one line report
        log.error("An error occurred: %s" % e)
    except Exception, e:
        # callstack
        log.exception("An error occurred: %s" % e)

    sys.exit(exit_code)
