"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Admin functions for working with versions of apps and engines.
Stuff like adding, updating and removing items from environments.

"""

from . import descriptor
from . import util
from .descriptor import AppDescriptor
from ..util import shotgun
from ..platform import constants
from ..platform import validation
from .. import pipelineconfig
from ..errors import TankError
from ..api import Tank

from tank_vendor import yaml

import sys
import os
import shutil


##########################################################################################
# core commands




def clone_configuration(log, tk, source_pc_id, user_id, name, target_linux, target_mac, target_win, source_pc_has_shared_core_api):
    """
    Clones the current configuration
    """

    curr_os = {"linux2":"linux_path", "win32":"windows_path", "darwin":"mac_path" }[sys.platform]    
    source_pc = tk.shotgun.find_one("PipelineConfiguration", 
                                    [["id", "is", source_pc_id]], 
                                    ["code", "project", "linux_path", "windows_path", "mac_path"])
    source_folder = source_pc.get(curr_os)
    
    target_folder = {"linux2":target_linux, "win32":target_win, "darwin":target_mac }[sys.platform] 
    
    log.debug("Cloning %s -> %s" % (source_folder, target_folder))
    
    if not os.path.exists(source_folder):
        raise TankError("Cannot clone! Source folder '%s' does not exist!" % source_folder)
    
    if os.path.exists(target_folder):
        raise TankError("Cannot clone! Target folder '%s' already exists!" % target_folder)
    
    # copy files and folders across
    old_umask = os.umask(0)
    try:
        os.mkdir(target_folder, 0777)
        os.mkdir(os.path.join(target_folder, "cache"), 0777)
        util._copy_folder(log, os.path.join(source_folder, "config"), os.path.join(target_folder, "config"))
        util._copy_folder(log, os.path.join(source_folder, "install"), os.path.join(target_folder, "install"))
        shutil.copy(os.path.join(source_folder, "tank"), os.path.join(target_folder, "tank"))
        shutil.copy(os.path.join(source_folder, "tank.bat"), os.path.join(target_folder, "tank.bat"))
        os.chmod(os.path.join(target_folder, "tank.bat"), 0777)
        os.chmod(os.path.join(target_folder, "tank"), 0777)

        sg_code_location = os.path.join(target_folder, "config", "core", "install_location.yml")
        if os.path.exists(sg_code_location):
            os.chmod(sg_code_location, 0666)
            os.remove(sg_code_location)
        fh = open(sg_code_location, "wt")
        fh.write("# Tank configuration file\n")
        fh.write("# This file was automatically created by tank clone\n")
        fh.write("# This file reflects the paths in the pipeline configuration\n")
        fh.write("# entity which is associated with this location (%s).\n" % name)
        fh.write("\n")
        fh.write("Windows: '%s'\n" % target_win)
        fh.write("Darwin: '%s'\n" % target_mac)    
        fh.write("Linux: '%s'\n" % target_linux)                    
        fh.write("\n")
        fh.write("# End of file.\n")
        fh.close()    
        os.chmod(sg_code_location, 0444)
    
    except Exception, e:
        raise TankError("Could not create file system structure: %s" % e)
    finally:
        os.umask(old_umask)

    # now register this with the cache file for each storage
    for dr in tk.pipeline_configuration.get_data_roots().values():
        scm = pipelineconfig.StorageConfigurationMapping(dr)
        scm.add_pipeline_configuration(target_mac, target_win, target_linux)
    
    # finally register with shotgun
    data = {"linux_path": target_linux,
            "windows_path":target_win,
            "mac_path": target_mac,
            "code": name,
            "project": source_pc["project"],
            "users": [ {"type": "HumanUser", "id": user_id} ] 
            }
    log.debug("Create sg: %s" % str(data))
    pc_entity = tk.shotgun.create("PipelineConfiguration", data)
    log.debug("Created in SG: %s" % str(pc_entity))

    # lastly, update the pipeline_configuration.yml file
    old_umask = os.umask(0)
    try:
        
        sg_pc_location = os.path.join(target_folder, "config", "core", "pipeline_configuration.yml")
        
        # read the file first
        fh = open(sg_pc_location, "rt")
        try:
            data = yaml.load(fh)
        finally:
            fh.close()

        # now delete it        
        if os.path.exists(sg_pc_location):
            os.chmod(sg_pc_location, 0666)
            os.remove(sg_pc_location)

        # now update some fields            
        data["pc_id"] = pc_entity["id"]
        data["pc_name"] = name 
        
        # and write the new file
        fh = open(sg_pc_location, "wt")
        yaml.dump(data, fh)
        fh.close()                        
        os.chmod(sg_pc_location, 0444)

    except Exception, e:
        raise TankError("Could not update pipeline_configuration.yml file: %s" % e)
    
    finally:
        os.umask(old_umask)
        
        

    log.info("<b>Clone Complete!</b>")
    log.info("")
    log.info("Your configuration has been copied from <code>%s</code> "
             "to <code>%s</code>." % (source_folder, target_folder))

    # if this new clone is using a shared core API, tell people how to localize.
    
    if source_pc_has_shared_core_api:
        log.info("")
        log.info("")
        log.info("<b>Note:</b> You are running a shared version of the Tank Core API for this new clone. "
                 "This means that when you make an upgrade to that shared API, all "
                 "the different projects that share it will be upgraded. This makes the upgrade "
                 "process quick and easy. However, sometimes you also want to break out of a shared "
                 "environment, for example if you want to test a new version of Tank. ")
        log.info("")
        log.info("In order to change this pipeline configuration to use its own independent version "
                 "of the Tank API, you can execute the following command: ")
    
        if sys.platform == "win32":
            tank_cmd = os.path.join(target_folder, "tank.bat")
        else:
            tank_cmd = os.path.join(target_folder, "tank")
        
        log.info("")
        code_css_block = "display: block; padding: 0.5em 1em; border: 1px solid #bebab0; background: #faf8f0;"
        log.info("<code style='%s'>%s core localize</code>" % (code_css_block, tank_cmd))



##########################################################################################
# helpers

g_sg_studio_version = None
def __get_sg_version():
    """
    Returns the version of the studio shotgun server.
    
    :returns: a string on the form "X.Y.Z"
    """
    global g_sg_studio_version
    if g_sg_studio_version is None:
        try:
            studio_sg = shotgun.create_sg_connection()
            g_sg_studio_version = ".".join([ str(x) for x in studio_sg.server_info["version"]])        
        except Exception, e:
            raise TankError("Could not extract version number for studio shotgun: %s" % e)
        
    return g_sg_studio_version

def _check_constraints(descriptor_obj, parent_engine_descriptor = None):
    """
    Checks if there are constraints blocking an upgrade or install
    
    :returns: a tuple: (can_upgrade, list_of_reasons)
    """
    
    constraints = descriptor_obj.get_version_constraints()
    
    can_update = True
    reasons = []
    
    if "min_sg" in constraints:
        # ensure shotgun version is ok
        studio_sg_version = __get_sg_version()
        minimum_sg_version = constraints["min_sg"]
        if util.is_version_older(studio_sg_version, minimum_sg_version):
            can_update = False
            reasons.append("Requires at least Shotgun v%s but currently "
                           "installed version is v%s." % (minimum_sg_version, studio_sg_version))
        
    if "min_core" in constraints:
        # ensure core API is ok
        core_api_version = pipelineconfig.get_core_api_version_based_on_current_code()
        minimum_core_version = constraints["min_core"]
        if util.is_version_older(core_api_version, minimum_core_version):
            can_update = False
            reasons.append("Requires at least Core API %s but currently "
                           "installed version is %s." % (minimum_core_version, core_api_version))
    
    if "min_engine" in constraints:
        curr_engine_version = parent_engine_descriptor.get_version()
        minimum_engine_version = constraints["min_engine"]
        if util.is_version_older(curr_engine_version, minimum_engine_version):
            can_update = False
            reasons.append("Requires at least Engine %s %s but currently "
                           "installed version is %s." % (parent_engine_descriptor.get_display_name(),
                                                        minimum_engine_version, 
                                                        curr_engine_version))
            
    # for multi engine apps, validate the supported_engines list
    supported_engines  = descriptor_obj.get_supported_engines()
    if supported_engines is not None:
        # this is a multi engine app!
        engine_name = parent_engine_descriptor.get_system_name()
        if engine_name not in supported_engines:
            can_update = False
            reasons.append("Not compatible with engine %s. "
                           "Supported engines are %s" % (engine_name, ", ".join(supported_engines)))
    
    return (can_update, reasons)


##########################################################################################
# public interface

def check_constraints_for_item(item_desc, environment_obj, engine_instance_name=None):
    """
    Validates the constraints for a single item. This will check that requirements for 
    minimum versions for shotgun, core API etc are fulfilled.
    
    Raises a TankError if one or more constraints are blocking. The exception message
    will contain details. 
    """
    
    # get the parent engine descriptor, if we are checking an app
    if engine_instance_name:
        # we are checking an engine object (it has no parent engine)
        parent_engine_descriptor = environment_obj.get_engine_descriptor(engine_instance_name)
    else:
        parent_engine_descriptor = None
        
    # check constraints (minimum versions etc)
    (can_update, reasons) = _check_constraints(item_desc, parent_engine_descriptor)
    
    if can_update == False:
        reasons.insert(0, "%s requires an upgrade to one or more "
                          "of your installed components." % item_desc)
        details = " ".join(reasons)
        raise TankError(details)



def check_item_update_status(environment_obj, engine_name, app_name = None):
    """
    Checks if an engine or app is up to date.
    Will locate the latest version of the item and run a comparison.
    Will check for constraints and report about these 
    (if the new version requires minimum version of shotgun, the core API, etc.)
    
    Returns a dictionary with the following keys:
    - current:       Current engine descriptor
    - latest:        Latest engine descriptor
    - out_of_date:   Is the current version out of date?
    - deprecated:    Is this item deprecated?
    - can_update:    Can we update?
    - update_status: String with details describing the status.  
    """
    if app_name is None:
        curr_desc = environment_obj.get_engine_descriptor(engine_name)
        parent_engine_desc = None
    else:
        curr_desc = environment_obj.get_app_descriptor(engine_name, app_name)
        # this is an app we are checking!
        # for apps, also get the descriptor for their parent engine
        parent_engine_desc = environment_obj.get_engine_descriptor(engine_name)

    # get latest version
    latest_desc = curr_desc.find_latest_version()

    # out of date check
    out_of_date = (latest_desc.get_version() != curr_desc.get_version())
    
    # check deprecation
    (is_dep, dep_msg) = latest_desc.get_deprecation_status()
    
    if is_dep:
        # we treat deprecation as an out of date that cannot be upgraded!
        out_of_date = True
        can_update = False
        status = "This item has been flagged as deprecated with the following status: %s" % dep_msg 

    elif not out_of_date:
        can_update = False
        status = "Item is up to date!"
    
    else:
        # maybe we can update!
        # look at constraints
        (can_update, reasons) = _check_constraints(latest_desc, parent_engine_desc)
        
        # create status message
        if can_update:
            status = "A new version (%s) of the item is available for installation." % latest_desc.get_version()
        else:
            reasons.insert(0, "The latest version (%s) of the item requires an upgrade to one "
                           "or more of your installed components." % latest_desc.get_version())
            status = " ".join(reasons)
            
    # prepare return data
    data = {}
    data["current"] = curr_desc
    data["latest"] = latest_desc
    data["out_of_date"] = out_of_date
    data["can_update"] = can_update
    data["update_status"] = status

    return data

def generate_settings_diff(new_descriptor, old_descriptor=None):
    """
    Returns a list of settings which are needed if we were to upgrade
    an environment based on old_descriptor to the one based on new_descriptor.
    
    Settings in the config which have default values will have their values
    populated in the return data structures.
    
    By omitting old_descriptor you will effectively diff against nothing, meaning
    that all the settings for the new version of the item (except default ones)
    will be part of the listing.
    
    Returns dict keyed by setting names. Each value is a dict with keys description and type:
    
    {
        "param1": {"description" : "a required param (no default)", "type": "str", value: None }
        "param1": {"description" : "an optional param (has default)", "type": "int", value: 123 }
    }
    
    """
    # get the new metadata (this will download the app potentially)
    schema = new_descriptor.get_configuration_schema()
    new_config_items = schema.keys()
    
    if old_descriptor is None:
        old_config_items = []
    else:
        try:
            old_schema = old_descriptor.get_configuration_schema()
            old_config_items = old_schema.keys()
        except TankError:
            # download to local failed? Assume that the old version is 
            # not valid. This is an edge case. 
            old_config_items = []
        
    
    new_parameters = set(new_config_items) - set(old_config_items)
    
    # add descriptions and types - skip default values!!!
    data = {}
    for x in new_parameters:        
        desc = schema[x].get("description", "No description.")
        schema_type = schema[x].get("type", "Unknown")
        default_val = schema[x].get("default_value")
        # check if allows_empty == True, in that case set default value to []
        if schema[x].get("allows_empty") == True:
            if default_val is None:
                default_val = []
        
        data[x] = {"description": desc, "type": schema_type, "value": default_val}
    return data
    
    
def validate_parameter(tank_api_instance, descriptor, parameter, str_value):
    """
    Convenience wrapper. Validates a single parameter.
    Will raise exceptions if validation fails.
    Returns the object-ified value on success.
    """
    
    schema = descriptor.get_configuration_schema()
    # get the type for the param we are dealing with
    schema_type = schema.get(parameter, {}).get("type", "unknown")
    # now convert string value input to objet (int, string, dict etc)
    obj_value = validation.convert_string_to_type(str_value, schema_type)
    # finally validate this object against the schema
    validation.validate_single_setting(descriptor.get_display_name(), tank_api_instance, schema, parameter, obj_value)
    
    # we are here, must mean we are good to go!
    return obj_value
    
    
    