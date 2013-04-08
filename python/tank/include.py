"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

include files management for template.yml and environment files.


includes
----------------------------------------------------------------------
includes are defined in the following sections in the data structure:

include: path
include: {path_data}

includes: [path, path]
includes: [path_data, path_data, path]

paths are on the following form:
----------------------------------------------------------------------
foo/bar.yml - local path, relative to current file
{Sequence}/{Shot}/hello.yml - template path based on context


path_data is on the following form:
----------------------------------------------------------------------
{path: path, required: false}


Template file includes
----------------------------------------------------------------------
If an include statement is found in a template file, the following will 
happen:

1. the included file will be read in (with recursive loading). The key, 
   path and string sections will be updated
2. as a second pass, any template starting with @xyz will be extended
   based on the referenced value
   
    
Environment file includes
----------------------------------------------------------------------
If an include statement is found in a template file, the following will 
happen:

all include files are read in.
if any value in the config refers to a @link, this will be looked up in the includes.


"""

SINGLE_INCLUDE_SECTION = "include"
MULTI_INCLUDE_SECTION = "includes"

TEMPLATE_SECTIONS = ["keys", "paths", "strings"]
TEMPLATE_PATH_SECTION = "paths"


import os
import re
import copy

from tank_vendor import yaml

from .errors import TankError
from .template import Template
from .templatekey import StringKey


def _get_includes(file_name, data):
    """
    Returns the includes in a data chunk.
    Returns a list of dicts with keys path and required
    """
    includes = []
    
    if SINGLE_INCLUDE_SECTION in data:
        # single include section
        includes.append( data[SINGLE_INCLUDE_SECTION] )
            
    if MULTI_INCLUDE_SECTION in data:
        # multi include section
        includes.extend( data[MULTI_INCLUDE_SECTION] )

    # validate
    for i in includes:

        # turn strings into dict forms
        if isinstance(i, basestring):
            i = {"path": i, "required": True}
        
        if not isinstance(i, dict):
            raise TankError("Syntax error in %s: invalid include: %s" % (file_name, str(i)))
        
        if not "path" in i.keys():
            raise TankError("Syntax error in %s: include missing path def: %s" % (file_name, str(i)))
        
        if not "required" in i.keys():
            raise TankError("Syntax error in %s: include missing required def: %s" % (file_name, str(i)))
    
    return includes

def _resolve_include_file(parent_file_path, path_def, context):
    """
    turns an include form into a proper path, adjusted for the OS.
    Supports the following formats:
    
    - foo/bar (relative to include file) 
    - {Shot}/foo (template based)
    
    """
    if "{" in path_def:
        # it's a template path
        
        # extract all {tokens}
        _key_name_regex = "[a-zA-Z_ 0-9]+"
        regex = r"(?<={)%s(?=})" % _key_name_regex
        key_names = re.findall(regex, path_def)

        try:
            # create template key objects        
            template_keys = {}
            for key_name in key_names:
                template_keys[key_name] = StringKey(key_name)
    
            # Make a template
            template = Template(path_def, template_keys)
        except TankError, e:
            raise TankError("Syntax error in %s: Could not transform include path '%s' "
                            "into a template: %s" % (parent_file_path, path_def, e))
        
        # and turn the template into a path based on the context
        try:
            f = context.as_template_fields(template)
            full_path = template.apply_fields(f)
        except TankError, e:
            raise TankError("Syntax error in %s: Could not transform include path '%s' (%s) "
                            "into a path using context %s: %s" % (parent_file_path, path_def, template, context, e))
            
    else:
        # local path
        adjusted = path_def.replace("/", os.path.sep)
        full_path = os.path.join(os.path.dirname(parent_file_path), adjusted)
    
    return full_path



def _process_template_includes_r(file_name, data, context):
    """
    Recursively add template include files.
    
    For each of the sections keys, strings, path, populate entries based on
    include files.
    
    """
    
    # return data    
    output_data = {}
    # add items for keys, paths, strings etc
    for ts in TEMPLATE_SECTIONS:
        output_data[ts] = {}
    
    # process includes
    includes = _get_includes(file_name, data)
    for i in includes:
                
        included_path = _resolve_include_file(file_name, i["path"], context)
        
        if not os.path.exists(included_path):
            if i["required"]:
                # must have this file
                raise TankError("Include Resolve error in %s: Resolved %s to %s, but "
                                "the path cannot be found" % (file_name, i["path"], included_path ))
            else:
                # optional include - ok to skip!
                continue
        
        # path exists, so try to read it
        fh = open(included_path, "r")
        try:
            included_data = yaml.load(fh) or {}
        finally:
            fh.close()
        
        # before doing any type of processing, allow the included data to be resolved.
        included_data = _process_template_includes_r(included_path, included_data, context)
        
        # add the included data's different sections
        for ts in TEMPLATE_SECTIONS:
            if ts in included_data:
                output_data[ts].update( included_data[ts] )
        
    # now all include data has been added into the data structure.
    # now add the template data itself
    for ts in TEMPLATE_SECTIONS:
        if ts in data:
            output_data[ts].update( data[ts] )
    
    return output_data
        

def get_template_str(data, template_name):
    """
    Returns a path str given a template name
    """
    for t in data[TEMPLATE_PATH_SECTION]:
        if t == template_name:
            d = data[TEMPLATE_PATH_SECTION][t]
            if isinstance(d, basestring):
                return d
            elif isinstance(d, dict):
                # maya_shot_work:
                #   definition: sequences/{Sequence}/{Shot}/{Step}/work/maya/{name}.v{version}.ma
                #   root_name: film
                return d["definition"]
            else:
                raise TankError("Invalid template definition %s. Please check config." % template_name)
    
    raise TankError("Could not resolve template reference @%s" % template_name)
    
        
def process_template_includes(file_name, data, context):
    """
    Processes includes for a data structure. Will look for 
    any include data structures and transform them into real data.    
    """
    
    # first recursively load all template data from includes
    resolved_includes_data = _process_template_includes_r(file_name, data, context)
    
    # now process any @resolves.
    # these are on the following form:
    # foo: bar
    # ttt: @foo/something
    # you can only use these in the paths section
    # you can only use them on the first item
    for t in resolved_includes_data[TEMPLATE_PATH_SECTION]:
        
        d = resolved_includes_data[TEMPLATE_PATH_SECTION][t]
        
        complex_syntax = False
        if isinstance(d, dict):
            template_str = d["definition"]
            complex_syntax = True
        elif isinstance(d, basestring):
            template_str = d
        else:
            raise TankError("Invalid template files configuration in %s for %s" % (file_name, t))
        
        if template_str.startswith("@"):
            # string template on the form 
            # maya_shot_work: @other_template/work/maya/{name}.v{version}.ma
            reference_template_name = d.split("/")[0][1:]
            # replace it with the resolved value
            val = get_template_str(resolved_includes_data, reference_template_name)
            rest_of_path = "/".join(d.split("/")[1:])
            resolved_template = "%s/%s" % (val, rest_of_path)
            
            # put the value back:
            if complex_syntax:
                resolved_includes_data[TEMPLATE_PATH_SECTION][t]["definition"] = resolved_template
            else:
                resolved_includes_data[TEMPLATE_PATH_SECTION][t] = resolved_template 
            
    return resolved_includes_data
        
        
################################################################################################        
        
        
        
        