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
include files management for template.yml

includes
----------------------------------------------------------------------
includes are defined in the following sections in the data structure:

include: path
includes: [path, path]


paths are on the following form:
----------------------------------------------------------------------
foo/bar.yml - local path, relative to current file

/foo/bar/hello.yml - absolute path, *nix
c:\foo\bar\hello.yml - absolute path, windows

"""



import os
import sys

from tank_vendor import yaml

from .errors import TankError
from .platform import constants


def _get_includes(file_name, data):
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
        
        if "/" in include and not include.startswith("/"):
            # relative path!
            adjusted = include.replace("/", os.path.sep)
            full_path = os.path.join(os.path.dirname(file_name), adjusted)
    
        elif "\\" in include:
            # windows absolute path
            if sys.platform != "win32":
                # ignore this on other platforms
                continue
            full_path = include
            
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


def _process_template_includes_r(file_name, data):
    """
    Recursively add template include files.
    
    For each of the sections keys, strings, path, populate entries based on
    include files.
    """
    
    # return data    
    output_data = {}
    # add items for keys, paths, strings etc
    for ts in constants.TEMPLATE_SECTIONS:
        output_data[ts] = {}
    
    # process includes
    included_paths = _get_includes(file_name, data)
    
    for included_path in included_paths:
                
        # path exists, so try to read it
        fh = open(included_path, "r")
        try:
            included_data = yaml.load(fh) or {}
        finally:
            fh.close()
        
        # before doing any type of processing, allow the included data to be resolved.
        included_data = _process_template_includes_r(included_path, included_data)
        
        # add the included data's different sections
        for ts in constants.TEMPLATE_SECTIONS:
            if ts in included_data:
                output_data[ts].update( included_data[ts] )
        
    # now all include data has been added into the data structure.
    # now add the template data itself
    for ts in constants.TEMPLATE_SECTIONS:
        if ts in data:
            output_data[ts].update( data[ts] )
    
    return output_data
        
def process_includes(file_name, data):
    """
    Processes includes for the main templates file. Will look for 
    any include data structures and transform them into real data.
    
    Algorithm (recursive):
    
    1. first load in include data into keys, strings, path sections.
       if there are multiple files, they are loaded in order.
    2. now, on top of this, load in this file's keys, strings and path defs
    3. lastly, process all @refs in the paths section
        
    """
    # first recursively load all template data from includes
    resolved_includes_data = _process_template_includes_r(file_name, data)
    
    # now recursively process any @resolves.
    # these are of the following form:
    # foo: bar
    # ttt: @foo/something
    # you can only use these in the paths section

    # process the template paths section:
    template_paths = resolved_includes_data[constants.TEMPLATE_PATH_SECTION] 
    for template_name in template_paths.keys():
        resolve_template_r(template_paths, template_name)
        
    # and process the strings section:
        
    return resolved_includes_data
        

def resolve_template_r(templates, template_name, template_chain = None):
    """
    Recursively resolve templates so that they are fully expanded.
    """

    # check we haven't searched this template before and keep 
    # track of the ones we have visited    
    visited_templates = template_chain or []
    if template_name in visited_templates:
        raise TankError("A cyclic template was found - template '%s' references itself (%s)" 
                        % (template_name, " -> ".join(visited_templates[visited_templates.index(template_name):] + [template_name])))
    visited_templates.append(template_name)
    
    # find the template definition:
    template_definition = templates.get(template_name)
    if not template_definition:
        raise TankError("Could not resolve template reference @%s" % template_name)
    
    # find the template string from the definition:
    template_str = None
    complex_syntax = False
    if isinstance(template_definition, dict):
        template_str = template_definition["definition"]
        complex_syntax = True
    elif isinstance(template_definition, basestring):
        template_str = template_definition
    if not template_str:
        raise TankError("Invalid template configuration for %s" % (template_name))
    
    # check for inline @ syntax:
    if template_str.startswith("@"):
        # string template of the form 
        # maya_shot_work: @other_template/work/maya/{name}.v{version}.ma
        template_parts = template_str.split("/")
        reference_template_name = template_parts[0][1:]
        
        # resolve the referenced template:
        resolved_template_str = resolve_template_r(templates, reference_template_name, visited_templates)
        
        rest_of_path = "/".join(template_parts[1:])
        resolved_template_str = "%s/%s" % (resolved_template_str, rest_of_path)
        
        # put the value back:
        if complex_syntax:
            templates[template_name]["definition"] = resolved_template_str
        else:
            templates[template_name] = resolved_template_str
            
        return resolved_template_str
    else:
        # just return the unmodified string:
        return template_str
    
    





    