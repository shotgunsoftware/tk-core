"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

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

from tank_vendor import yaml

from ..errors import TankError
from ..template import Template
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
    
            try:
                # create template key objects        
                template_keys = {}
                for key_name in key_names:
                    template_keys[key_name] = StringKey(key_name)
        
                # Make a template
                template = Template(include, template_keys)
            except TankError, e:
                raise TankError("Syntax error in %s: Could not transform include path '%s' "
                                "into a template: %s" % (file_name, include, e))
            
            # and turn the template into a path based on the context
            try:
                f = context.as_template_fields(template)
                full_path = template.apply_fields(f)
            except TankError, e:
                raise TankError("Syntax error in %s: Could not transform include path '%s' (%s) "
                                "into a path using context %s: %s" % (file_name, include, template, context, e))
            
            if not os.path.exists(full_path):
                # skip - these paths are optional always
                continue                
        
        elif "/" in include and not include.startswith("/"):
            # relative path!
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
            full_path = include
            # make sure that the paths all exist
            if not os.path.exists(full_path):
                raise TankError("Include Resolve error in %s: Included path %s "
                                "does not exist!" % (file_name, full_path))
            
        else:
            # linux absolute path
            if sys.platform == "win32":
                # ignore this on other platforms
                continue
            full_path = include                    
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
        
        processed_val = lookup_dict[ref_token]
        
    return processed_val
            


        
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
        resolved_data = _resolve_refs_r(lookup_dict, data)
    except TankError, e:
        raise TankError("Include error. Could not resolve references for %s: %s" % (file_name, e))
    
    return resolved_data
    
    
    
    
    