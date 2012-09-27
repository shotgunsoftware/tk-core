"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Admin functions for working with versions of apps and engines.
Stuff like adding, updating and removing items from environments.

"""

from . import descriptor
from .descriptor import AppDescriptor
from ..util import shotgun
from ..platform import constants
from ..platform import validation
from ..errors import TankError
from ..api import Tank

from distutils.version import LooseVersion

##########################################################################################
# helpers

g_sg_studio_version = None
def __get_sg_version(project_root):
    """
    Returns the version of the studio shotgun server.
    
    :returns: a string on the form "X.Y.Z"
    """
    global g_sg_studio_version
    if g_sg_studio_version is None:
        try:
            studio_sg = shotgun.create_sg_connection(project_root)
            g_sg_studio_version = ".".join([ str(x) for x in studio_sg.server_info["version"]])        
        except Exception, e:
            raise TankError("Could not extract version number for studio shotgun: %s" % e)
        
    return g_sg_studio_version

def _check_constraints(project_root, descriptor_obj, parent_engine_descriptor = None):
    """
    Checks if there are constraints blocking an upgrade or install
    
    :returns: a tuple: (can_upgrade, list_of_reasons)
    """
    
    constraints = descriptor_obj.get_version_constraints()
    
    can_update = True
    reasons = []
    
    if "min_sg" in constraints:
        # ensure shotgun version is ok
        studio_sg_version = __get_sg_version(project_root)
        minimum_sg_version = constraints["min_sg"]
        # strip the v off the shotgun version if there is one
        if minimum_sg_version.startswith("v"):
            minimum_sg_version = minimum_sg_version[1:]
            
        if LooseVersion(studio_sg_version) < LooseVersion(minimum_sg_version):
            can_update = False
            reasons.append("Requires at least Shotgun v%s but currently "
                           "installed version is v%s." % (minimum_sg_version, studio_sg_version))
        
    if "min_core" in constraints:
        # ensure core API is ok
        core_api_version = constants.get_core_api_version()
        minimum_core_version = constraints["min_core"]
        
        if LooseVersion(core_api_version) < LooseVersion(minimum_core_version):
            can_update = False
            reasons.append("Requires at least Core API %s but currently "
                           "installed version is %s." % (minimum_core_version, core_api_version))
    
    if "min_engine" in constraints:
        curr_engine_version = parent_engine_descriptor.get_version()
        minimum_engine_version = constraints["min_engine"]
        
        if LooseVersion(curr_engine_version) < LooseVersion(minimum_engine_version):
            can_update = False
            reasons.append("Requires at least Engine %s %s but currently "
                           "installed version is %s." % (parent_engine_descriptor.get_display_name(),
                                                        minimum_engine_version, 
                                                        curr_engine_version))
            
    # for multi engine apps, validate the supported_engines list
    md  = descriptor_obj.get_metadata()
    if "supported_engines" in md:
        # this is a multi engine app!
        supported_engines = md["supported_engines"]
        engine_name = parent_engine_descriptor.get_short_name()
        if engine_name not in supported_engines:
            can_update = False
            reasons.append("Not compatible with engine %s. "
                           "Supported engines are %s" % (engine_name, ", ".join(supported_engines)))
    
    return (can_update, reasons)


##########################################################################################
# public interface

def check_constraints_for_item(project_root, item_desc, environment_obj, engine_instance_name=None):
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
    (can_update, reasons) = _check_constraints(project_root, item_desc, parent_engine_descriptor)
    
    if can_update == False:
        reasons.insert(0, "%s requires an upgrade to one or more "
                          "of your installed components." % item_desc)
        details = " ".join(reasons)
        raise TankError(details)



def check_item_update_status(project_root, environment_obj, engine_name, app_name = None):
    """
    Checks if an engine or app is up to date.
    Will locate the latest version of the item and run a comparison.
    Will check for constraints and report about these 
    (if the new version requires minimum version of shotgun, the core API, etc.)
    
    Returns a dictionary with the following keys:
    - current:       Current engine descriptor
    - latest:        Latest engine descriptor
    - out_of_date:   Is the current version out of date?
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

    if not out_of_date:
        can_update = False
        status = "Engine is up to date!"
    
    else:
        # maybe we can update!
        # look at constraints
        (can_update, reasons) = _check_constraints(project_root, latest_desc, parent_engine_desc)
        
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
    # get the new metadata (this will download the app pontentially)
    new_meta = new_descriptor.get_metadata()
    new_config_items = new_meta["configuration"].keys()
    
    if old_descriptor is None:
        old_config_items = []
    else:
        try:
            old_meta = old_descriptor.get_metadata()
            old_config_items = old_meta["configuration"].keys()
        except TankError:
            # download to local failed? Assume that the old version is 
            # not valid. This is an edge case. 
            old_config_items = []
        
    
    new_parameters = set(new_config_items) - set(old_config_items)
    
    # add descriptions and types - skip default values!!!
    data = {}
    for x in new_parameters:        
        desc = new_meta["configuration"][x].get("description", "No description.")
        schema_type = new_meta["configuration"][x].get("type", "Unknown")
        default_val = new_meta["configuration"][x].get("default_value")
        # check if allows_empty == True, in that case set default value to []
        if new_meta["configuration"][x].get("allows_empty") == True:
            if default_val is None:
                default_val = []
        
        data[x] = {"description": desc, "type": schema_type, "value": default_val}
    return data
    
    
def validate_parameter(project_root, descriptor, parameter, str_value):
    """
    Convenience wrapper. Validates a single parameter.
    Will raise exceptions if validation fails.
    Returns the object-ified value on success.
    """
    
    new_meta = descriptor.get_metadata()
    schema = new_meta["configuration"]
    # get the type for the param we are dealing with
    schema_type = schema.get(parameter, {}).get("type", "unknown")
    # now convert string value input to objet (int, string, dict etc)
    obj_value = validation.convert_string_to_type(str_value, schema_type)
    # finally validate this object against the schema
    tk_api = Tank(project_root)
    schema = new_meta["configuration"]
    validation.validate_single_setting(descriptor.get_display_name(), tk_api, schema, parameter, obj_value)
    
    # we are here, must mean we are good to go!
    return obj_value
    
    
    
    