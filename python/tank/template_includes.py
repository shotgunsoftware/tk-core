"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

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
        

def get_template_str(data, template_name):
    """
    Returns a path str given a template name
    """
    for t in data[constants.TEMPLATE_PATH_SECTION]:
        if t == template_name:
            d = data[constants.TEMPLATE_PATH_SECTION][t]
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
    
    # now process any @resolves.
    # these are on the following form:
    # foo: bar
    # ttt: @foo/something
    # you can only use these in the paths section
    # you can only use them on the first item
    for t in resolved_includes_data[constants.TEMPLATE_PATH_SECTION]:
        
        d = resolved_includes_data[constants.TEMPLATE_PATH_SECTION][t]
        
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
                resolved_includes_data[constants.TEMPLATE_PATH_SECTION][t]["definition"] = resolved_template
            else:
                resolved_includes_data[constants.TEMPLATE_PATH_SECTION][t] = resolved_template 
            
    return resolved_includes_data
        
        
    