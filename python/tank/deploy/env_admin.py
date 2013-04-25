"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

App and engine management.

"""

from . import administrator
from . import console_utils

from ..platform import constants
from ..errors import TankError

from .descriptor import AppDescriptor
from .app_store_descriptor import TankAppStoreDescriptor

import sys
import os
import shutil


def install_app(log, tk, env_name, engine_instance_name, app_name):
    """
    installs an app
    """
    
    log.info("")
    log.info("")
    log.info("Welcome to the Tank App installer!")
    log.info("")

    try:
        env = tk.pipeline_configuration.get_environment(env_name)
    except Exception, e:
        raise TankError("Environment '%s' could not be loaded! Error reported: %s" % (env_name, e))

    # make sure the engine exists in the environment
    if engine_instance_name not in env.get_engines():
        raise TankError("Environment %s has no engine named %s!" % (env_name, engine_instance_name))

    # find engine
    app_descriptor = TankAppStoreDescriptor.find_item(tk.pipeline_configuration, AppDescriptor.APP, app_name)
    log.info("Successfully located %s..." % app_descriptor)
    log.info("")

    # note! Some of these methods further down are likely to pull the apps local
    # in order to do deep introspection. In order to provide better error reporting,
    # pull the apps local before we start
    if not app_descriptor.exists_local():
        log.info("Downloading from App Store, hold on...")
        app_descriptor.download_local()
        log.info("")

    # now assume a convention where we will name the app instance that we create in the environment
    # the same as the short name of the app
    app_instance_name = app_descriptor.get_system_name()

    # check so that there is not an app with that name already!
    if app_instance_name in env.get_apps(engine_instance_name):
        raise TankError("Engine %s already has an app named %s!" % (engine_instance_name, app_instance_name))

    # now make sure all constraints are okay
    try:
        administrator.check_constraints_for_item(app_descriptor, env, engine_instance_name)
    except TankError, e:
        raise TankError("Cannot install: %s" % e)

    # okay to install!
    
    # ensure that all required frameworks have been installed
    console_utils.ensure_frameworks_installed(log, tk, app_descriptor, env)

    # create required shotgun fields
    app_descriptor.ensure_shotgun_fields_exist()

    # now get data for all new settings values in the config
    params = console_utils.get_configuration(log, tk, app_descriptor, None)

    # next step is to add the new configuration values to the environment
    env.create_app_settings(engine_instance_name, app_instance_name)
    env.update_app_settings(engine_instance_name, app_instance_name, params, app_descriptor.get_location())

    log.info("")
    log.info("")
    log.info("App Installation Complete!")
    log.info("")
    if app_descriptor.get_doc_url():
        log.info("For documentation, see %s" % app_descriptor.get_doc_url())
    log.info("")
    log.info("")
    
    
def install_engine(log, tk, env_name, engine_name):
    """
    installs an engine
    """
    log.info("")
    log.info("")
    log.info("Welcome to the Tank Engine installer!")
    log.info("")

    try:
        env = tk.pipeline_configuration.get_environment(env_name)
    except Exception, e:
        raise TankError("Environment '%s' could not be loaded! Error reported: %s" % (env_name, e))

    # find engine
    engine_descriptor = TankAppStoreDescriptor.find_item(tk.pipeline_configuration, AppDescriptor.ENGINE, engine_name)
    log.info("Successfully located %s..." % engine_descriptor)
    log.info("")

    # now assume a convention where we will name the engine instance that we create in the environment
    # the same as the short name of the engine
    engine_instance_name = engine_descriptor.get_system_name()

    # check so that there is not an app with that name already!
    if engine_instance_name in env.get_engines():
        raise TankError("Engine %s already exists in environment %s!" % (engine_instance_name, env))

    # now make sure all constraints are okay
    try:
        administrator.check_constraints_for_item(engine_descriptor, env)
    except TankError, e:
        raise TankError("Cannot install: %s" % e)


    # okay to install!

    # ensure that all required frameworks have been installed
    console_utils.ensure_frameworks_installed(log, tk, engine_descriptor, env)

    # note! Some of these methods further down are likely to pull the apps local
    # in order to do deep introspection. In order to provide better error reporting,
    # pull the apps local before we start
    if not engine_descriptor.exists_local():
        log.info("Downloading from App Store, hold on...")
        engine_descriptor.download_local()
        log.info("")

    # create required shotgun fields
    engine_descriptor.ensure_shotgun_fields_exist()

    # now get data for all new settings values in the config
    params = console_utils.get_configuration(log, tk, engine_descriptor, None)
    
    # next step is to add the new configuration values to the environment
    env.create_engine_settings(engine_instance_name)
    env.update_engine_settings(engine_instance_name, params, engine_descriptor.get_location())

    log.info("")
    log.info("")
    log.info("Engine Installation Complete!")
    log.info("")
    if engine_descriptor.get_doc_url():
        log.info("For documentation, see %s" % engine_descriptor.get_doc_url())
    log.info("")
    log.info("")

    
    
    
    

def _update_item(log, tk, env, status, engine_name, app_name=None):
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
    console_utils.ensure_frameworks_installed(log, tk, new_descriptor, env)

    # now get data for all new settings values in the config
    params = console_utils.get_configuration(log, tk, new_descriptor, old_descriptor)

    # awesome. got all the values we need.
    log.info("")
    log.info("")

    # next step is to add the new configuration values to the environment
    if app_name is None:

        data = env.get_engine_settings(engine_name)
        # update with the new settings
        data.update(params)
        env.update_engine_settings(engine_name, data, new_descriptor.get_location())

    else:

        data = env.get_app_settings(engine_name, app_name)
        # update with the new settings
        data.update(params)
        env.update_app_settings(engine_name, app_name, data, new_descriptor.get_location())

def _process_framework(log, env, framework_name):
    """
    Ensures that a framework exists on disk.
    """
    log.info("Processing framework %s" % framework_name)
    desc = env.get_framework_descriptor(framework_name)
    
    if not desc.exists_local():
        log.info("Downloading %s..." % desc)
        desc.download_local() 


def _process_item(log, tk, env, engine_name, app_name=None):
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

    status = administrator.check_item_update_status(env, engine_name, app_name)
    item_was_updated = False

    if status["can_update"]:
        
        # print summary of changes
        console_utils.format_bundle_info(log, status["latest"])
        
        # ask user
        if console_utils.ask_question("Update to the above version?"):
            _update_item(log, tk, env, status, engine_name, app_name)
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


def check_for_updates(log, tk):
    """
    Check for updates.
    """

    log.info("Welcome to the Tank update checker!")
    log.info("This script will check that all apps and engines are up to date.")
    log.info("")

    pc = tk.pipeline_configuration
    environments = [ pc.get_environment(x) for x in pc.get_environments()]

    # check engines and apps
    items = []
    for env in environments:
        log.info("")
        log.info("Processing Environment %s..." % env.name)
        log.info("")
                
        for engine in env.get_engines():
            items.append( _process_item(log, tk, env, engine) )
            log.info("")
            for app in env.get_apps(engine):
                items.append( _process_item(log, tk, env, engine, app) )
                log.info("")
        
        for framework in env.get_frameworks():
            _process_framework(log, env, framework)
        

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
    