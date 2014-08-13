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
Encapsulates the pipeline configuration and helps navigate and resolve paths
across storages, configurations etc.
"""
import os
import sys

from tank_vendor import yaml

from .errors import TankError


def is_localized(pipeline_config_path):
    """
    Returns true if the pipeline configuration contains a localized API
    
    :param pipeline_config_path: path to a pipeline configuration root folder
    :returns: true if localized, false if not
    """
    # look for a localized API by searching for a _core_upgrader.py file
    api_file = os.path.join(pipeline_config_path, "install", "core", "_core_upgrader.py")
    return os.path.exists(api_file)

####################################################################################################################
# Core API resolve utils 

def get_path_to_current_core():
    """
    Returns the local path of the currently executing code, assuming that this code is 
    located inside a standard toolkit install setup. If the code that is running is part
    of a localized pipeline configuration, the PC root path will be returned, otherwise 
    a 'studio' root will be returned.
    
    This method may not return valid results if there has been any symlinks set up as part of
    the install structure.
    
    :returns: string with path
    """
    curr_os_core_root = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "..", "..", ".."))
    if not os.path.exists(curr_os_core_root):
        full_path_to_file = os.path.abspath(os.path.dirname(__file__))
        raise TankError("Cannot resolve the core configuration from the location of the Toolkit Code! "
                        "This can happen if you try to move or symlink the Toolkit API. The "
                        "Toolkit API is currently picked up from %s which is an "
                        "invalid location." % full_path_to_file)
    return curr_os_core_root    
    
    
def get_core_path_for_config(pipeline_config_path):
    """
    Returns the core api install location associated with the given pipeline configuration.
    In the case of a localized PC, it just returns the given path.
    Otherwise, it resolves the location via the core_xxxx.cfg files.
    
    :param pipeline_config_path: path to a pipeline configuration
    :returns: Path to the studio location root or pipeline configuration root or None if not resolved
    """

    if is_localized(pipeline_config_path):
        # first, try to locate an install local to this pipeline configuration.
        # this would find any localized APIs.
        install_path = pipeline_config_path

    else:
        # this PC is associated with a shared API (studio install)
        # follow the links defined in the configuration to establish which 
        # setup it has been associated with.
        studio_linkback_files = {"win32": os.path.join(pipeline_config_path, "install", "core", "core_Windows.cfg"), 
                                 "linux2": os.path.join(pipeline_config_path, "install", "core", "core_Linux.cfg"), 
                                 "darwin": os.path.join(pipeline_config_path, "install", "core", "core_Darwin.cfg")}
        
        curr_linkback_file = studio_linkback_files[sys.platform]
        
        # this file will contain the path to the API which is meant to be used with this PC.
        install_path = None
        try:
            fh = open(curr_linkback_file, "rt")
            data = fh.read().strip() # remove any whitespace, keep text
            # expand any env vars that are used in the files. For example, you could have 
            # an env variable $STUDIO_TANK_PATH=/sgtk/software/shotgun/studio and your 
            # linkback file may just contain "$STUDIO_TANK_PATH" instead of an explicit path.
            data = os.path.expandvars(data)
            if data not in ["None", "undefined"] and os.path.exists(data):
                install_path = data
            fh.close()  
        except:
            pass
                
    return install_path
    
    
def resolve_all_os_paths_to_core(core_path):
    """
    Given a core path on the current os platform, return paths on all platforms,
    as cached in the install_locations system file
    
    :returns: dictionary with keys linux2, darwin and win32
    """
    return _get_install_locations(core_path)

def _get_install_locations(path):
    """
    Given a pipeline configuration OR core location, return paths on all platforms.
    
    :returns: dictionary with keys linux2, darwin and win32
    """
    
    # basic sanity check
    if not os.path.exists(path):
        raise TankError("The core path '%s' does not exist on disk!" % path)
    
    # for other platforms, read in install_location
    location_file = os.path.join(path, "config", "core", "install_location.yml")
    if not os.path.exists(location_file):
        raise TankError("Cannot find core config file '%s' - please contact support!" % location_file)

    # load the config file
    try:
        open_file = open(location_file)
        try:
            location_data = yaml.load(open_file)
        finally:
            open_file.close()
    except Exception, error:
        raise TankError("Cannot load core config file '%s'. Error: %s" % (location_file, error))

    # do some cleanup on this file - sometimes there are entries that say "undefined"
    # or is just an empty string - turn those into null values
    linux_path = location_data.get("Linux")
    macosx_path = location_data.get("Darwin")
    win_path = location_data.get("Windows")
    
    if not linux_path or not linux_path.startswith("/"):
        linux_path = None
    if not macosx_path or not macosx_path.startswith("/"):
        macosx_path = None
    if not win_path or not (win_path.startswith("\\") or win_path[1] == ":"):
        win_path = None

    # return data
    return {"win32": win_path, "darwin": macosx_path, "linux2": linux_path }
        



####################################################################################################################
# utils for determining core version numbers

def get_currently_running_api_version():
    """
    Returns the version number string for the core API, 
    based on the code that is currently executing.
    
    :returns: version string, e.g. 'v1.2.3'. 'unknown' if a version number cannot be determined.
    """
    # read this from info.yml
    info_yml_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "info.yml"))
    return _get_version_from_manifest(info_yml_path)


def get_core_api_version(core_install_root):
    """
    Returns the version string for the core api associated with this config.
    This method is 'forgiving' and in the case no associated core API can be 
    found for this location, 'unknown' will be returned rather than 
    an exception raised. 

    :param core_install_root: Path to a core installation root, either the root of a pipeline
                              configuration, or the root of a "bare" studio code location.
    :returns: version str e.g. 'v1.2.3', 'unknown' if no version could be determined. 
    """
    # now try to get to the info.yml file to get the version number
    info_yml_path = os.path.join(core_install_root, "install", "core", "info.yml")
    return _get_version_from_manifest(info_yml_path)
    
def _get_version_from_manifest(info_yml_path):
    """
    Helper method. 
    Returns the version given a manifest.
    
    :param info_yml_path: path to manifest file.
    :returns: Always a string, 'unknown' if data cannot be found
    """
    try:
        info_fh = open(info_yml_path, "r")
        try:
            data = yaml.load(info_fh)
        finally:
            info_fh.close()
        data = str(data.get("version", "unknown"))
    except:
        data = "unknown"

    return data
    
