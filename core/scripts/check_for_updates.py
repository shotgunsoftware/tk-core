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

##########################################################################################
# helpers

g_ask_questions = True

def _ask_question(question, force_promt=False):
    """
    Ask a yes-no-always question
    returns true if user pressed yes (or previously always)
    false if no
    """
    global g_ask_questions
    if g_ask_questions == False and force_promt == False:
        # auto-press YES
        return True

    answer = raw_input("%s [Yna?]" % question)
    answer = answer.lower()
    if answer != "n" and answer != "a" and answer != "y" and answer != "":
        print("Press ENTER or y for YES, n for NO and a for ALWAYS.")
        answer = raw_input("%s [Yna?]" % question)

    if answer == "a":
        g_ask_questions = False
        return True

    if answer == "y" or answer == "":
        return True

    return False


def _format_bundle_info(log, info, summary):
    """
    Formats a release notes summary output for an app, engine or core
    """
    log.info("/%s" % ("-" * 70))
    log.info("| Item:    %s" % info)
    str_to_wrap = "Summary: %s" % summary
    for x in textwrap.wrap(str_to_wrap, width=68, initial_indent="| ", subsequent_indent="|          "):
        log.info(x)
    log.info("\%s" % ("-" * 70))

def _format_param_info(log, name, type, summary):
    """
    Formats a release notes summary output for an app, engine or core
    """
    log.info("/%s" % ("-" * 70))
    log.info("| Setting: %s" % name)
    log.info("| Type:    %s" % type)
    str_to_wrap = "Summary: %s" % summary
    for x in textwrap.wrap(str_to_wrap, width=68, initial_indent="| ", subsequent_indent="|          "):
        log.info(x)
    log.info("\%s" % ("-" * 70))

##########################################################################################
# deploy stuff

def update_item(log, project_root, env, status, engine_name, app_name=None):
    """
    Performs an upgrade of an engine/app.
    """

    # note! Some of these methods further down are likely to pull the apps local
    # in order to do deep introspection. In order to provide better error reporting,
    # pull the apps local before we start
    if not status["latest"].exists_local():
        log.info("Downloading %s..." % status["latest"])
        status["latest"].download_local()

    # create required shotgun fields
    status["latest"].ensure_shotgun_fields_exist(project_root)

    # first get data for all new parameter values in the config
    param_diff = administrator.generate_settings_diff(status["latest"], status["current"])
    if len(param_diff) > 0:
        log.info("")
        log.info("Note! Several new settings were added in the new version of the app.")
        log.info("")

    params = {}
    for (name, data) in param_diff.items():
        # output info about the setting
        log.info("")
        _format_param_info(log, name, data["type"], data["description"])

        # don't ask user to input anything for default values
        if data["value"] is not None:
            value = data["value"]
            if data["type"] == "hook":
                value = status["latest"].install_hook(log, value)
            params[name] = value
            # note that value can be a tuple so need to cast to str
            log.info("Auto-populated with default value '%s'" % str(value))

        else:

            # get value from user
            # loop around until happy
            input_valid = False
            while not input_valid:
                # ask user
                answer = raw_input("Please enter value (enter to skip): ")
                if answer == "":
                    # user chose to skip
                    log.warning("You skipped this value! Please update the environment by hand later!")
                    params[name] = None
                    input_valid = True
                else:
                    # validate value
                    try:
                        obj_value = administrator.validate_parameter(project_root, status["latest"], name, answer)
                    except Exception, e:
                        log.error("Validation failed: %s" % e)
                    else:
                        input_valid = True
                        params[name] = obj_value

    # awesome. got all the values we need.
    log.info("")
    log.info("")

    # next step is to add the new configuration values to the environment
    if app_name is None:

        data = env.get_engine_settings(engine_name)
        data.update(params)
        env.update_engine_settings(engine_name, data)
        env.update_engine_location(engine_name, status["latest"].get_location())

    else:

        data = env.get_app_settings(engine_name, app_name)
        data.update(params)
        env.update_app_settings(engine_name, app_name, data)
        env.update_app_location(engine_name, app_name, status["latest"].get_location())

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
        # yay we can install! - get release notes
        (summary, url) = status["latest"].get_changelog()
        if summary is None:
            summary = "No details provided."
        _format_bundle_info(log, status["latest"], summary)
        if _ask_question("Update to the above version?"):
            update_item(log, project_root, env, status, engine_name, app_name)
            item_was_updated = True

    elif status["out_of_date"] == False and not status["current"].exists_local():
        # app is not local! boo!
        if _ask_question("Current version does not exist locally - download it now?"):
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
