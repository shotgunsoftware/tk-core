"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

App and engine management.

"""

from . import descriptor
from . import util
from .descriptor import AppDescriptor
from .app_store_descriptor import TankAppStoreDescriptor
from ..util import shotgun
from ..platform import constants
from ..platform import validation
from .. import pipelineconfig
from ..errors import TankError
from ..api import Tank
from . import administrator
from . import console_utils

import sys
import os
import shutil


##########################################################################################
# core commands




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
    env.update_app_settings(engine_instance_name, app_instance_name, params)
    env.update_app_location(engine_instance_name, app_instance_name, app_descriptor.get_location())

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
    env.update_engine_settings(engine_instance_name, params)
    env.update_engine_location(engine_instance_name, engine_descriptor.get_location())

    log.info("")
    log.info("")
    log.info("Engine Installation Complete!")
    log.info("")
    if engine_descriptor.get_doc_url():
        log.info("For documentation, see %s" % engine_descriptor.get_doc_url())
    log.info("")
    log.info("")

    