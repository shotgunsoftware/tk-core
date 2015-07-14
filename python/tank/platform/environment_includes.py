# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
include files management for template.yml and environment files.

includes
----------------------------------------------------------------------
includes are defined in the following sections in the data structure:

include: path
includes: [path, path]

paths are on the following form:
----------------------------------------------------------------------
foo/bar.yml - local path, relative to current file
{Sequence}/{Shot}/hello.yml - template path based on context

relative paths are always required and context based paths are always optional.

"""


import os
import re
import sys
import copy 

from tank_vendor import yaml

from ..errors import TankError
from ..template import TemplatePath
from ..templatekey import StringKey

from . import constants

from ..util.yaml_cache import g_yaml_cache

def _resolve_includes(file_name, data, context):
    """
    Parses the includes section and returns a list of valid paths
    """
    includes = []
    resolved_includes = []
    
    if constants.SINGLE_INCLUDE_SECTION in data:
        # single include section
        includes.append( data[constants.SINGLE_INCLUDE_SECTION] )
            
    if constants.MULTI_INCLUDE_SECTION in data:
        # multi include section
        includes.extend( data[constants.MULTI_INCLUDE_SECTION] )

    for include in includes:
        
        if "{" in include:
            # it's a template path
            if context is None:
                # skip - these paths are optional always
                continue
            
            # extract all {tokens}
            _key_name_regex = "[a-zA-Z_ 0-9]+"
            regex = r"(?<={)%s(?=})" % _key_name_regex
            key_names = re.findall(regex, include)
    
            # get all the data roots for this project
            # note - it is possible that this call may raise an exception for configs
            # which don't have a primary storage defined - this is logical since such
            # configurations cannot make use of references into the file system hierarchy
            # (because no such hierarchy exists)
            primary_data_root = context.tank.pipeline_configuration.get_primary_data_root()
    
            # try to construct a path object for each template
            try:
                # create template key objects        
                template_keys = {}
                for key_name in key_names:
                    template_keys[key_name] = StringKey(key_name)
        
                # Make a template
                template = TemplatePath(include, template_keys, primary_data_root)
            except TankError, e:
                raise TankError("Syntax error in %s: Could not transform include path '%s' "
                                "into a template: %s" % (file_name, include, e))
            
            # and turn the template into a path based on the context
            try:
                f = context.as_template_fields(template)
                full_path = template.apply_fields(f)
            except TankError, e:
                # if this path could not be resolved, that's ok! These paths are always optional.
                continue
            
            if not os.path.exists(full_path):
                # skip - these paths are optional always
                continue       
        
        elif "/" in include and not include.startswith("/") and not include.startswith("$"):
            # relative path: foo/bar.yml or ./foo.bar.yml
            # note the $ check to avoid paths beginning with env vars to fall into this branch
            adjusted = include.replace("/", os.path.sep)
            full_path = os.path.join(os.path.dirname(file_name), adjusted)
            # make sure that the paths all exist
            if not os.path.exists(full_path):
                raise TankError("Include Resolve error in %s: Included path %s ('%s') "
                                "does not exist!" % (file_name, full_path, include))
    
        elif "\\" in include:
            # windows absolute path
            if sys.platform != "win32":
                # ignore this on other platforms
                continue
            full_path = os.path.expandvars(include)
            # make sure that the paths all exist
            if not os.path.exists(full_path):
                raise TankError("Include Resolve error in %s: Included path %s "
                                "does not exist!" % (file_name, full_path))
            
        else:
            # linux absolute path
            if sys.platform == "win32":
                # ignore this on other platforms
                continue
            full_path = os.path.expandvars(include)                    
            # make sure that the paths all exist
            if not os.path.exists(full_path):
                raise TankError("Include Resolve error in %s: Included path %s "
                                "does not exist!" % (file_name, full_path))

        resolved_includes.append(full_path)

    return resolved_includes



def _resolve_refs_r(lookup_dict, data):
    """
    Scans data for @refs and attempts to replace based on lookup data
    """
    # default is no processing
    processed_val = data
    
    if isinstance(data, list):
        processed_val = []
        for x in data:
            processed_val.append(_resolve_refs_r(lookup_dict, x))
    
    elif isinstance(data, dict):
        processed_val = {}
        for (k,v) in data.items():
            processed_val[k] = _resolve_refs_r(lookup_dict, v)
        
    elif isinstance(data, basestring) and data.startswith("@"):
        # this is a reference!
        
        ref_token = data[1:]
        if ref_token not in lookup_dict:
            raise TankError("Undefined Reference %s!" % ref_token)
        # other parts of the code is making changes nilly-willy to data
        # structures (ick) so flatten everything out here.... :(
        processed_val = copy.deepcopy(lookup_dict[ref_token])
        
    return processed_val
            
def _resolve_frameworks(lookup_dict, data):
    """
    Resolves any framework related includes
    """
    if "frameworks" in lookup_dict:
        # cool, we got some frameworks in our lookup section
        # add them to the main data

        fw = lookup_dict["frameworks"]
        if "frameworks" not in data:
            data["frameworks"] = {}
        if data["frameworks"] is None:
            data["frameworks"] = {}
        data["frameworks"].update(fw)    
    
    return data
    

def process_includes(file_name, data, context):
    """
    Process includes for an environment file.
    
    :param file_name:   The root yml file to process
    :param data:        The contents of the root yml file to process
    :param context:     The current context
    
    :returns:           The flattened yml data after all includes have
                        been recursively processed.
    """
    # call the recursive method:
    data, _ = _process_includes_r(file_name, data, context)
    return data
        
def _process_includes_r(file_name, data, context):
    """
    Recursively process includes for an environment file.
    
    Algorithm (recursive):
    
    1. Load include data into a big dictionary X
    2. recursively go through the current file and replace any 
       @ref with a dictionary value from X
    
    :param file_name:   The root yml file to process
    :param data:        The contents of the root yml file to process
    :param context:     The current context

    :returns:           A tuple containing the flattened yml data 
                        after all includes have been recursively processed
                        together with a lookup for frameworks to the file 
                        they were loaded from.
    """
    # first build our big fat lookup dict
    include_files = _resolve_includes(file_name, data, context)
    
    lookup_dict = {}
    fw_lookup = {}
    for include_file in include_files:
                
        # path exists, so try to read it
        included_data = g_yaml_cache.get(include_file) or {}
                
        # now resolve this data before proceeding
        included_data, included_fw_lookup = _process_includes_r(include_file, included_data, context)

        # update our big lookup dict with this included data:
        if "frameworks" in included_data and isinstance(included_data["frameworks"], dict):
            # special case handling of frameworks to merge them from the various
            # different included files rather than have frameworks section from
            # one file overwrite the frameworks from previous includes!
            lookup_dict = _resolve_frameworks(included_data, lookup_dict)

            # also, keey track of where the framework has been referenced from:
            for fw_name in included_data["frameworks"].keys():
                fw_lookup[fw_name] = include_file

            del(included_data["frameworks"])

        fw_lookup.update(included_fw_lookup)
        lookup_dict.update(included_data)
    
    # now go through our own data, recursively, and replace any refs.
    # recurse down in dicts and lists
    try:
        data = _resolve_refs_r(lookup_dict, data)
        data = _resolve_frameworks(lookup_dict, data)
    except TankError, e:
        raise TankError("Include error. Could not resolve references for %s: %s" % (file_name, e))
    
    return data, fw_lookup
    

def find_framework_location(file_name, framework_name, context):
    """
    Find the location of the instance of a framework that will
    be used after all includes have been resolved.
    
    :param file_name:       The root yml file
    :param framework_name:  The name of the framework to find
    :param context:         The current context
    
    :returns:               The yml file that the framework is 
                            defined in or None if not found.
    """
    # load the data in for the root file:
    data = g_yaml_cache.get(file_name)

    # track root frameworks:
    root_fw_lookup = {}
    fw_data = data.get("frameworks", {})
    if fw_data and isinstance(fw_data, dict):
        for fw in fw_data.keys():
            root_fw_lookup[fw] = file_name 

    # process includes and get the lookup table for the frameworks:        
    _, fw_lookup = _process_includes_r(file_name, data, context)
    root_fw_lookup.update(fw_lookup)
    
    # return the location of the framework if we can
    return root_fw_lookup.get(framework_name) or None
    
def find_reference(file_name, context, token):
    """
    Non-recursive. Looks at all include files and searches
    for @token. Returns the file in which it is found.
    """
    
    # load the data in 
    data = g_yaml_cache.get(file_name)
    
    # first build our big fat lookup dict
    include_files = _resolve_includes(file_name, data, context)
    
    found_file = None
    
    for include_file in include_files:
                
        # path exists, so try to read it
        included_data = g_yaml_cache.get(include_file) or {}
        
        if token in included_data:
            found_file = include_file
        
    return found_file
    
    
    
