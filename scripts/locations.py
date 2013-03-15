"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Edits the locations parameter for apps and engines.
Makes it easy to switch to dev versions of apps and code.

"""

import os
import sys
import logging
import textwrap

# make sure that the core API is part of the pythonpath
python_path = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "python"))
sys.path.append(python_path)

import tank
from tank.errors import TankError
from tank.platform import constants
from tank.platform import environment
from tank.deploy import administrator
from tank.deploy import console_utils
from tank.deploy import descriptor
from tank.deploy.descriptor import AppDescriptor
from tank.deploy.app_store_descriptor import TankAppStoreDescriptor
from tank.deploy.dev_descriptor import TankDevDescriptor


##########################################################################################
# deploy stuff

def _show_item(log, type, instance_name, descriptor):
    log.info("")
    loc_dict = descriptor.get_location()
    indent = ""
    if type == "app":
        indent = "    "
    elif type == "engine":
        log.info("-" * 80)
        
    log.info("%s[%s] - %s %s %s. Location: %s" % (indent,
                                          instance_name,
                                          type.capitalize(), 
                                          descriptor.get_system_name(), 
                                          descriptor.get_version(), 
                                          loc_dict.get("type")))
    log.info("%s Summary: %s" % (indent, descriptor.get_description()))
    log.info("%s Path: %s" % (indent, descriptor.get_path()))

    

def show_breakdown(log, env_obj):
    
    log.info("Below is a breakdown of all the items found in the environment")
    log.info("and the code associated with each item.")
    log.info("")

    log.info("")
    log.info("=" * 80)
    log.info("Engines & Apps (%d engines found)" % len(env_obj.get_engines()))
    log.info("=" * 80)

    for eng_inst in env_obj.get_engines():        
        desc = env_obj.get_engine_descriptor(eng_inst)
        _show_item(log, "engine", eng_inst, desc)
        
        for app_inst in env_obj.get_apps(eng_inst):
            desc = env_obj.get_app_descriptor(eng_inst, app_inst)
            _show_item(log, "app", app_inst, desc)
            
    log.info("")
    log.info("=" * 80)
    log.info("Frameworks (%d found)" % len(env_obj.get_frameworks()))
    log.info("=" * 80)
    for fw_inst in env_obj.get_frameworks():
        desc = env_obj.get_framework_descriptor(fw_inst)
        _show_item(log, "framework", fw_inst, desc)
        
def switch_location(log, project_root, env_obj, app_name, engine_name, framework_name, path):
    """
    Switches a location for an existing entry
    """
    
    # find the current descriptor
    if framework_name:
        mode = AppDescriptor.FRAMEWORK
        try:
            curr_desc = env_obj.get_framework_descriptor(framework_name)
        except TankError:
            log.info("Framework %s not found - will add it to the environment." % framework_name)
            curr_desc = None
            env_obj.create_framework_settings(framework_name)
        
    elif app_name:
        mode = AppDescriptor.APP
        try:
            curr_desc = env_obj.get_app_descriptor(engine_name, app_name)
        except TankError:
            log.info("App %s not found - will add it to the environment." % app_name)
            curr_desc = None        
            env_obj.create_app_settings(engine_name, app_name)
        
    else:
        mode = AppDescriptor.ENGINE
        try:
            curr_desc = env_obj.get_engine_descriptor(engine_name)
        except TankError:
            log.info("Engine %s not found - will add it to the environment." % engine_name)
            curr_desc = None
            env_obj.create_engine_settings(engine_name)
        
    
    #  find the new item
    if path is None:
        # find latest app store item based on prev descriptor
        if curr_desc is None:
            # no entry in the environment
            raise TankError("Cannot find item in environment! In order to install new items "
                            "from the app store, use the dedicated script for this.")
        
        log.info("Reverting to latest app store version...")
        new_desc = TankAppStoreDescriptor.find_item(project_root, mode, curr_desc.get_system_name())
    
    else:
        # dev version
        log.info("Looking for code in %s..." % path)
        new_desc = TankDevDescriptor.from_path(project_root, path)
    
    log.info("Successfully located %s..." % new_desc)
    if not new_desc.exists_local():
        log.info("Downloading %s..." % new_desc)
        new_desc.download_local()
    
    
    # create required shotgun fields
    new_desc.ensure_shotgun_fields_exist()

    # ensure that all required frameworks have been installed
    tank_api = tank.Tank(project_root)
    console_utils.ensure_frameworks_installed(log, tank_api, new_desc, env_obj)

    # now get data for all new settings values in the config
    params = console_utils.get_configuration(log, tank_api, new_desc, curr_desc)

    # awesome. got all the values we need.
    log.info("")
    log.info("")

    # next step is to add the new configuration values to the environment
    if mode == AppDescriptor.APP:

        data = env_obj.get_app_settings(engine_name, app_name)
        # update with the new settings
        data.update(params)
        env_obj.update_app_settings(engine_name, app_name, data)
        env_obj.update_app_location(engine_name, app_name, new_desc.get_location())


    elif mode == AppDescriptor.FRAMEWORK:
        data = env_obj.get_framework_settings(framework_name)
        # update with the new settings
        data.update(params)
        env_obj.update_framework_settings(framework_name, data)
        env_obj.update_framework_location(framework_name, new_desc.get_location())
    
    elif mode == AppDescriptor.ENGINE:
        
        data = env_obj.get_engine_settings(engine_name)
        # update with the new settings
        data.update(params)
        env_obj.update_engine_settings(engine_name, data)
        env_obj.update_engine_location(engine_name, new_desc.get_location())
    
    else:
        raise TankError("Unknown type!")

    
    log.info("Location switch complete!")
    



##########################################################################################
# main script and startup

def main(log):
    """
    App entry point
    """

    if len(sys.argv) != 3 and len(sys.argv) != 5:
        log.info("")
        log.info("")
        log.info("Shows the code locations for apps, engines and frameworks.")
        log.info("")
        log.info("Usage: %s project_root environment_name [params]" % sys.argv[0])
        log.info("")
        log.info("Example - Show an overview:       > python %s project_root environment_name" % sys.argv[0])
        log.info("Example - Start dev on an engine: > python %s project_root environment_name tk-nuke /home/username/tank_dev/tk-nuke" % sys.argv[0])
        log.info("Example - Start dev on an app:    > python %s project_root environment_name tk-nuke.tk-nuke-publish /home/username/tank_dev/tk-nuke-publish" % sys.argv[0])
        log.info("Example - Stop dev on an engine:  > python %s project_root environment_name tk-nuke app_store" % sys.argv[0])
        log.info("Example - Stop dev on app:        > python %s project_root environment_name tk-nuke.tk-nuke-publish app_store" % sys.argv[0])
        log.info("")
        log.info("If you want to add a new app to the environment, just use the same syntax:")
        log.info("> python %s project_root environment_name tk-nuke.tk-nuke-newapp /home/username/tank_dev/tk-nuke-newapp" % sys.argv[0])
        log.info("")
        log.info("")
        sys.exit(1)

    log.info("Welcome to the Tank location tool.")
    log.info("")

    if len(sys.argv) == 3:
        # show an overview
        project_root = sys.argv[1]
        env_name = sys.argv[2]
        log.info("This script will display all the code locations for all items")
        log.info("in project %s, environment %s" % (project_root, env_name))

        try:
            env_file = constants.get_environment_path(env_name, project_root)
            env_obj = environment.Environment(env_file)
        except Exception, e:
            raise TankError("Environment %s could not be loaded! Error reported: %s" % (env_name, e))

        log.info("")
        log.info("")
    
        show_breakdown(log, env_obj)
        
        log.info("")
        log.info("=" * 80)
        log.info("Modifying Locations")
        log.info("=" * 80)
        log.info("")
        log.info("You can use this script to change the location of an item ")
        log.info("in an environment. For example, if you want to do development ")
        log.info("on an app that exists in the environment, do the following:")
        log.info("")
        log.info("* Download the app code to a local location, e.g. /home/user/tank_dev/tk-nuke-publish")
        log.info("* Find the [instance] in the list above that refers to that app. Typically, ")
        log.info("  the instance has the same name as the app itself, eg. tk-nuke-publish")
        log.info("* Find the engine [instance] that the app belogs to, e.g. tk-nuke")
        log.info("* execute this command with parameters:")
        log.info("  > %s %s %s tk-nuke.tk-nuke-publish /home/user/tank_dev/tk-nuke-publish" % (sys.argv[0],
                                                                                             project_root, 
                                                                                             env_name))
        
        log.info("* The above command will switch the configuration to use the local dev code")
        log.info("  and also make sure that all required frameworks and parameters have been ")
        log.info("  correctly configured.")
        
        log.info("")
        log.info("Alternatively, if you want to do development on an app that is not yet in the ")
        log.info("environment, just execute the same command.")
        log.info("")
        log.info("If you want to switch an item in dev mode back to use the Tank Store again, ")
        log.info("just execute the same command as above but use 'app_store' instead of a path: ")
        log.info("  > %s %s %s tk-nuke.tk-nuke-publish app_store" % (sys.argv[0],
                                                                     project_root, 
                                                                     env_name))

    elif len(sys.argv) == 5:
        # do an actual switch!
        project_root = sys.argv[1]
        env_name = sys.argv[2]
        item = sys.argv[3]
        path = sys.argv[4]
        
        try:
            env_file = constants.get_environment_path(env_name, project_root)
            env_obj = environment.Environment(env_file)
        except Exception, e:
            raise TankError("Environment %s could not be loaded! Error reported: %s" % (env_name, e))

        framework = None
        engine = None
        app = None
        if item.startswith("tk-framework"):
            framework = item
        elif "." in item:
            try:
                (engine, app) = item.split(".")
            except:
                raise TankError("Could not interpret the string %s as an app string!" % item)
        else:
            engine = item
        
        if path == "app_store":
            switch_location(log, project_root, env_obj, app, engine, framework, None)
        else:
            switch_location(log, project_root, env_obj, app, engine, framework, path)   

    log.info("")


if __name__ == "__main__":

    log = logging.getLogger("tank.locations")
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
