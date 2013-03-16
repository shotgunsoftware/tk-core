"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Constants relating to the Tank API and low level systems.

"""

import os


################################################################################################
# constants

CONTENT_TEMPLATES_FILE = "templates.yml"
ROOTS_FILE = "roots.yml" # If multiple roots are defined, do so in this file

################################################################################################
# methods for accessing constants

def get_content_templates_location(pipeline_configuration_path):
    """
    returns the location of the content templates file
    """
    return os.path.join(pipeline_configuration_path, "config", "core", CONTENT_TEMPLATES_FILE)

def get_core_hooks_folder(pipeline_configuration_path):
    """
    returns the core hooks folder for the project
    """
    return os.path.join(pipeline_configuration_path, "config", "core", "hooks")

def get_roots_file_location(project_path): 
    """ 
    returns the location of the roots file 
    """ 
    return os.path.join(project_path, "tank", "config", "core", ROOTS_FILE)