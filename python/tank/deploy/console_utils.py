"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Helper methods for asking the user for input.
This is a temporary file which will go away once the deploy is handled by an app

"""

import os
import sys
import logging
import textwrap

from . import administrator
from ..platform import validation
from ..platform import constants
from ..errors import TankError
from .app_store_descriptor import TankAppStoreDescriptor
from .descriptor import AppDescriptor


def get_configuration(log, tank_api_instance, new_ver_descriptor, old_ver_descriptor):
    """
    Retrieves all the parameters needed for an app, engine or framework.
    May prompt the user for information.
    """
    
    # first get data for all new settings values in the config
    param_diff = administrator.generate_settings_diff(new_ver_descriptor, old_ver_descriptor)

    if len(param_diff) > 0:
        log.info("Several new settings are associated with %s." % new_ver_descriptor)
        log.info("You will now be prompted to input values for all settings")
        log.info("that do not have default values defined.")
        log.info("")

    params = {}
    for (name, data) in param_diff.items():

        ######
        # output info about the setting
        log.info("")
        log.info("/%s" % ("-" * 70))
        log.info("| Item:    %s" % name)
        log.info("| Type:    %s" % data["type"])
        str_to_wrap = "Summary: %s" % data["description"]
        for x in textwrap.wrap(str_to_wrap, width=68, initial_indent="| ", subsequent_indent="|          "):
            log.info(x)
        log.info("\%s" % ("-" * 70))
        

        # don't ask user to input anything for default values
        if data["value"] is not None:
            
            if data["type"] == "hook":
                # for hooks, instead set the value to "default"
                # this means that the app will use its local hooks
                # rather than the ones provided.
                value = constants.TANK_BUNDLE_DEFAULT_HOOK_SETTING
            else:
                # just copy the default value into the environment
                value = data["value"]
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
                        obj_value = administrator.validate_parameter(tank_api_instance, 
                                                                     new_ver_descriptor, 
                                                                     name, 
                                                                     answer)
                    except Exception, e:
                        log.error("Validation failed: %s" % e)
                    else:
                        input_valid = True
                        params[name] = obj_value
    

    return params



g_ask_questions = True

def ask_question(question, force_promt=False):
    """
    Ask a yes-no-always question
    returns true if user pressed yes (or previously always)
    false if no
    
    if force_prompt is True, it always ask, regardless of if the user
    has previously pressed [a]lways
    
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


def format_bundle_info(log, descriptor):
    """
    Formats a release notes summary output for an app, engine or core
    """
    
    # yay we can install! - get release notes
    (summary, url) = descriptor.get_changelog()
    if summary is None:
        summary = "No details provided."
    
    
    log.info("/%s" % ("-" * 70))
    log.info("| Item:        %s" % descriptor)
    log.info("|")
    
    str_to_wrap = "Description: %s" % descriptor.get_description()
    for x in textwrap.wrap(str_to_wrap, width=68, initial_indent="| ", subsequent_indent="|              "):
        log.info(x)
    log.info("|")
    
    str_to_wrap = "Change Log:  %s" % summary
    for x in textwrap.wrap(str_to_wrap, width=68, initial_indent="| ", subsequent_indent="|              "):
        log.info(x)
    
    log.info("\%s" % ("-" * 70))


def ensure_frameworks_installed(log, tank_api_instance, descriptor, environment):
    """
    Recursively check that all required frameworks are installed.
    Anything not installed will be downloaded from the app store.
    """
    missing_fws = validation.get_missing_frameworks(descriptor, environment)
    # (this returns dictionaries with name and version keys)
    
    for fw_dict in missing_fws:
        
        # see if we can get this from the app store...
        fw_descriptor = TankAppStoreDescriptor.find_item(tank_api_instance.pipeline_configuration, 
                                                         AppDescriptor.FRAMEWORK, 
                                                         fw_dict["name"], 
                                                         fw_dict["version"])
        
        
        # and now process this framework
        log.info("Installing required framework %s..." % fw_descriptor)
        if not fw_descriptor.exists_local():
            fw_descriptor.download_local()
        
        # now assume a convention where we will name the fw_instance that we create in the environment
        # on the form name_version
        fw_instance_name = "%s_%s" % (fw_descriptor.get_system_name(), fw_descriptor.get_version())
    
        # check so that there is not an fw with that name already!
        if fw_instance_name in environment.get_frameworks():
            raise TankError("The environment already has a framework instance named %s! "
                            "Please contact support." % fw_instance_name)
    
        # now make sure all constraints are okay
        try:
            administrator.check_constraints_for_item(fw_descriptor, environment)
        except TankError, e:
            raise TankError("Cannot install framework: %s" % e)
    
        # okay to install!
    
        # create required shotgun fields
        fw_descriptor.ensure_shotgun_fields_exist()
    
        # now get data for all new settings values in the config
        params = get_configuration(log, tank_api_instance, fw_descriptor, None)
    
        # next step is to add the new configuration values to the environment
        environment.create_framework_settings(fw_instance_name, params, fw_descriptor.get_location())
        
        # now make sure these guys have all their required frameworks installed
        ensure_frameworks_installed(log, tank_api_instance, fw_descriptor, environment)
        
    
    
    