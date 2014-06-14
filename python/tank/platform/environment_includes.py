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
    Processes includes for an environment file.
    
    Algorithm (recursive):
    
    1. Load include data into a big dictionary X
    2. recursively go through the current file and replace any 
       @ref with a dictionary value from X
    
    """
    
    # first build our big fat lookup dict
    include_files = _resolve_includes(file_name, data, context)
    
    lookup_dict = {}
    for include_file in include_files:
                
        # path exists, so try to read it
        fh = open(include_file, "r")
        try:
            included_data = yaml.load(fh) or {}
        finally:
            fh.close()
                
        # now resolve this data before proceeding
        included_data = process_includes(include_file, included_data, context)
        
        # update our big lookup dict with this data
        lookup_dict.update(included_data)
    
    # now go through our own data, recursively, and replace any refs.
    # recurse down in dicts and lists
    try:
        data = _resolve_refs_r(lookup_dict, data)
        data = _resolve_frameworks(lookup_dict, data)
    except TankError, e:
        raise TankError("Include error. Could not resolve references for %s: %s" % (file_name, e))
    
    return data
    
    
def find_reference(file_name, context, token):
    """
    Non-recursive. Looks at all include files and searches
    for @token. Returns the file in which it is found.
    """
    
    # load the data in 
    try:
        fh = open(file_name, "r")
        data = yaml.load(fh)
    except Exception, exp:
        raise TankError("Could not parse file %s. Error reported: %s" % (file_name, exp))
    finally:
        fh.close()
    
    # first build our big fat lookup dict
    include_files = _resolve_includes(file_name, data, context)
    
    found_file = None
    
    for include_file in include_files:
                
        # path exists, so try to read it
        fh = open(include_file, "r")
        try:
            included_data = yaml.load(fh) or {}
        finally:
            fh.close()
        
        if token in included_data:
            found_file = include_file
        
    return found_file
    
    
    
